"""ARCPClient: handshake driver, request/response correlation, event tail and fan-out."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .._envelope import Envelope
from .._errors import (
    InvalidRequestError,
    error_from_payload,
)
from .._logger import get_logger
from .._messages.execution import (
    JobAcceptedPayload,
    Lease,
    LeaseConstraints,
)
from .._messages.session import (
    AuthBearer,
    Capabilities,
    ClientInfo,
    ListJobsFilter,
    SessionHelloPayload,
    SessionJobsPayload,
    SessionResume,
    SessionWelcomePayload,
)
from .._runtime.pending import PendingRegistry
from .._transport.base import Transport, TransportClosed
from .._ulid import new_envelope_id
from .._version import V1_1_FEATURES, intersect_features
from .handles import JobHandle, JobSubscription

_LOG = get_logger("arcp.client")

def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

@dataclass(frozen=True)
class AutoAckOptions:
    """Coalesce acks: send `session.ack` every `every_n` events, or every `interval_sec`."""

    every_n: int = 100
    interval_sec: float = 1.0

class ARCPClient:
    """ARCP client: open/resume a session, submit jobs, observe events."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        client: ClientInfo,
        token: str,
        capabilities: Capabilities | None = None,
        features: tuple[str, ...] | None = None,
        auto_ack: AutoAckOptions | bool = False,
        handshake_timeout_sec: float = 5.0,
        logger: Any = None,
    ) -> None:
        # PLR0913: every arg is an optional, keyword-only config knob.
        # Grouping into a config dataclass would break callers without
        # improving clarity. TODO(arcp/v2): revisit on major bump.
        self.client_info = client
        self.token = token
        self.features = features if features is not None else V1_1_FEATURES
        self.capabilities = capabilities or Capabilities(
            encodings=("json",), features=self.features
        )
        self.auto_ack: AutoAckOptions | None = (
            AutoAckOptions()
            if auto_ack is True
            else (auto_ack if isinstance(auto_ack, AutoAckOptions) else None)
        )
        self.handshake_timeout_sec = handshake_timeout_sec
        self.logger = logger or _LOG

        self._transport: Transport | None = None
        self._welcome: SessionWelcomePayload | None = None
        self._session_id: str | None = None
        self._negotiated: tuple[str, ...] = ()
        self._handles: dict[str, JobHandle] = {}
        self._subscriptions: dict[str, JobSubscription] = {}
        self._pending: PendingRegistry = PendingRegistry()
        self._read_task: asyncio.Task[Any] | None = None
        self._auto_ack_task: asyncio.Task[Any] | None = None
        self._highest_seq: int = 0
        self._pending_accepts: deque[asyncio.Future[JobAcceptedPayload]] = deque()
        self._closed = False
        self._dispatch_cache: dict[str, Callable[[Envelope], Awaitable[None]]] | None = None

    @property
    def negotiated_features(self) -> tuple[str, ...]:
        return self._negotiated

    def has_feature(self, name: str) -> bool:
        return name in self._negotiated

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def welcome(self) -> SessionWelcomePayload | None:
        return self._welcome

    async def connect(self, transport: Transport) -> SessionWelcomePayload:
        """Send `session.hello`, await `session.welcome`, start the read pump."""
        return await self._handshake(transport, resume=None)

    async def resume(self, transport: Transport, *, resume: SessionResume) -> SessionWelcomePayload:
        """Resume an existing session."""
        return await self._handshake(transport, resume=resume)

    async def _handshake(
        self, transport: Transport, *, resume: SessionResume | None
    ) -> SessionWelcomePayload:
        self._transport = transport
        hello = SessionHelloPayload(
            client=self.client_info,
            auth=AuthBearer(token=self.token),
            capabilities=self.capabilities,
            resume=resume,
        )
        env = Envelope(
            id=new_envelope_id(),
            type="session.hello",
            payload=hello.model_dump(mode="json", exclude_none=True),
        )
        await transport.send(env.to_wire())
        async with asyncio.timeout(self.handshake_timeout_sec):
            raw = await transport.recv()
        reply = Envelope.from_wire(raw)
        if reply.type == "session.error":
            raise error_from_payload(reply.payload)
        if reply.type != "session.welcome":
            raise InvalidRequestError(f"expected session.welcome, got {reply.type!r}")
        welcome = SessionWelcomePayload.model_validate(reply.payload)
        self._welcome = welcome
        self._session_id = welcome.session_id
        self._negotiated = intersect_features(self.features, welcome.capabilities.features)

        self._read_task = asyncio.create_task(self._read_pump())
        if self.auto_ack is not None and "ack" in self._negotiated:
            self._auto_ack_task = asyncio.create_task(self._auto_ack_loop())
        return welcome

    async def _read_pump(self) -> None:
        assert self._transport is not None
        try:
            while not self._closed:
                raw = await self._transport.recv()
                env = Envelope.from_wire(raw)
                if env.event_seq is not None and env.event_seq > self._highest_seq:
                    self._highest_seq = env.event_seq
                await self._dispatch(env)
        except TransportClosed:
            self._fail_all_handles(TransportClosed("transport closed"))
        except Exception as e:
            self.logger.exception("client_read_pump_failed", error=str(e))
            self._fail_all_handles(e)

    async def _dispatch(self, env: Envelope) -> None:
        handler = self._dispatch_table().get(env.type)
        if handler is not None:
            await handler(env)

    def _dispatch_table(self) -> dict[str, Callable[[Envelope], Awaitable[None]]]:
        if self._dispatch_cache is None:
            from .dispatch import build_dispatch_table

            self._dispatch_cache = build_dispatch_table(self)
        return self._dispatch_cache

    def _fail_all_handles(self, exc: BaseException) -> None:
        for h in list(self._handles.values()):
            h._reject_terminal(exc)
        self._handles.clear()
        for fut in list(self._pending_accepts):
            if not fut.done():
                fut.set_exception(exc)
        self._pending_accepts.clear()
        self._pending.cancel_all(exc)

    async def _auto_ack_loop(self) -> None:
        assert self.auto_ack is not None
        last_acked = 0
        try:
            while not self._closed:
                await asyncio.sleep(self.auto_ack.interval_sec)
                if self._highest_seq - last_acked >= self.auto_ack.every_n:
                    await self.ack(self._highest_seq)
                    last_acked = self._highest_seq
        except asyncio.CancelledError:
            return

    async def submit(  # noqa: PLR0913
        self,
        *,
        agent: str,
        input: Any = None,
        lease_request: Lease | None = None,
        lease_constraints: LeaseConstraints | None = None,
        idempotency_key: str | None = None,
        max_runtime_sec: int | None = None,
        trace_id: str | None = None,
        parent_job_id: str | None = None,
    ) -> JobHandle:
        # PLR0913: all kwargs map one-to-one onto a protocol payload's
        # optional fields. Bundling them in a dataclass for one operation
        # removes ergonomics with no clarity gain.
        from .ops import submit_job

        return await submit_job(
            self,
            agent=agent,
            input=input,
            lease_request=lease_request,
            lease_constraints=lease_constraints,
            idempotency_key=idempotency_key,
            max_runtime_sec=max_runtime_sec,
            trace_id=trace_id,
            parent_job_id=parent_job_id,
        )

    async def cancel_job(self, job_id: str, *, reason: str = "client.cancel") -> None:
        from .ops import cancel_job

        await cancel_job(self, job_id, reason=reason)

    async def list_jobs(
        self,
        *,
        filter: ListJobsFilter | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> SessionJobsPayload:
        from .ops import list_jobs

        return await list_jobs(self, filter=filter, limit=limit, cursor=cursor)

    async def subscribe(
        self,
        job_id: str,
        *,
        history: bool = False,
        from_event_seq: int | None = None,
    ) -> JobSubscription:
        from .ops import subscribe

        return await subscribe(self, job_id, history=history, from_event_seq=from_event_seq)

    async def unsubscribe(self, job_id: str) -> None:
        from .ops import unsubscribe

        await unsubscribe(self, job_id)

    async def ack(self, last_processed_seq: int) -> None:
        from .ops import ack

        await ack(self, last_processed_seq)

    @property
    def latest_event_seq(self) -> int:
        return self._highest_seq

    async def close(self, *, reason: str = "client.close") -> None:
        from .ops import close_session

        await close_session(self, reason=reason)

    async def aclose(self) -> None:
        await self.close()

__all__ = ("ARCPClient", "AutoAckOptions")
