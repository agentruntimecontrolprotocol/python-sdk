"""ARCP client — handshake driver and command dispatcher (RFC §5)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import structlog

from arcp.envelope import Envelope
from arcp.errors import ARCPError, ErrorCode
from arcp.messages.session import (
    AuthBlock,
    Capabilities,
    Identity,
    SessionAcceptedPayload,
    SessionOpenPayload,
)
from arcp.transport.base import Transport, TransportClosed

logger = structlog.get_logger("arcp.client")


def _new_msg_id() -> str:
    return f"msg_{uuid.uuid4().hex[:12]}"


@dataclass
class ARCPClient:
    """Async ARCP client.

    The client owns one :class:`Transport` and one event-loop reader task that
    routes inbound envelopes to either:

    * a per-correlation_id ``asyncio.Future`` registered before sending a
      command that expects a response, or
    * a tail :class:`asyncio.Queue` exposed via :meth:`events`.
    """

    transport: Transport
    client_identity: Identity
    auth: AuthBlock
    capabilities: Capabilities = field(default_factory=Capabilities)
    session_id: str | None = None
    runtime: dict[str, Any] | None = None
    _negotiated: Capabilities | None = None
    _waiters: dict[str, asyncio.Future[Envelope]] = field(
        default_factory=dict[str, asyncio.Future[Envelope]]
    )
    _events: asyncio.Queue[Envelope | None] = field(
        default_factory=lambda: asyncio.Queue[Envelope | None]()
    )
    _reader_task: asyncio.Task[None] | None = None
    _closed: bool = False

    @property
    def negotiated_capabilities(self) -> Capabilities:
        if self._negotiated is None:
            raise RuntimeError("client has not completed handshake")
        return self._negotiated

    async def open(self) -> SessionAcceptedPayload:
        """Drive the §8.1 handshake. Returns the accepted-session payload."""

        if self.session_id is not None:
            raise RuntimeError("client is already open")
        open_envelope = Envelope(
            id=_new_msg_id(),
            type="session.open",
            payload=SessionOpenPayload(
                auth=self.auth,
                client=self.client_identity,
                capabilities=self.capabilities,
            ).model_dump(exclude_none=True),
        )
        await self.transport.send(open_envelope.to_wire())

        # The runtime may emit either session.challenge → session.authenticate
        # → session.accepted, or session.accepted directly. v0.1 supports the
        # direct path; the challenge branch is wired through but unused.
        while True:
            raw = await self.transport.recv()
            response = Envelope.from_wire(raw)
            if response.correlation_id != open_envelope.id:
                # Out-of-band envelope before handshake completes — drop.
                logger.debug("ignoring pre-accept envelope", message_type=response.type)
                continue

            if response.type == "session.accepted":
                accepted = SessionAcceptedPayload.model_validate(response.payload)
                self.session_id = accepted.session_id
                self.runtime = accepted.runtime.model_dump(exclude_none=True)
                self._negotiated = accepted.capabilities
                self._reader_task = asyncio.create_task(self._reader_loop())
                return accepted

            if response.type == "session.rejected":
                raise ARCPError(
                    ErrorCode(response.payload.get("code", "UNAUTHENTICATED")),
                    response.payload.get("message", "session rejected"),
                )

            if response.type == "session.challenge":
                # Echo authenticate using same credentials. Sufficient for v0.1
                # since challenge responses for bearer/JWT degenerate to
                # presenting the same token (real CR-style nonces are
                # implementation-defined and out of scope).
                authn = Envelope(
                    id=_new_msg_id(),
                    type="session.authenticate",
                    correlation_id=response.id,
                    payload={"auth": self.auth.model_dump(exclude_none=True)},
                )
                await self.transport.send(authn.to_wire())
                continue

            raise ARCPError(
                ErrorCode.INTERNAL,
                f"unexpected envelope during handshake: {response.type!r}",
            )

    async def send(self, envelope: Envelope) -> None:
        """Send an envelope on the bound transport."""

        if self.session_id is None:
            raise RuntimeError("client is not open")
        await self.transport.send(envelope.to_wire())

    async def request(
        self,
        envelope: Envelope,
        *,
        timeout: float | None = None,  # noqa: ASYNC109 — public API; pass-through to asyncio.timeout below.
    ) -> Envelope:
        """Send a command and await the envelope whose ``correlation_id`` matches.

        ``correlation_id`` matching is keyed on the outbound envelope's ``id``.
        """

        if self.session_id is None:
            raise RuntimeError("client is not open")
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Envelope] = loop.create_future()
        self._waiters[envelope.id] = future
        try:
            await self.transport.send(envelope.to_wire())
            async with asyncio.timeout(timeout):
                return await future
        finally:
            self._waiters.pop(envelope.id, None)

    async def events(self) -> AsyncIterator[Envelope]:
        """Yield non-correlated envelopes (events, streams, etc.)."""

        while True:
            envelope = await self._events.get()
            if envelope is None:
                return
            yield envelope

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._events.put(None)
        if self._reader_task is not None:
            self._reader_task.cancel()
            with _suppress(asyncio.CancelledError):
                await self._reader_task
        with _suppress(Exception):
            await self.transport.close()

    async def _reader_loop(self) -> None:
        try:
            while not self._closed:
                try:
                    raw = await self.transport.recv()
                except TransportClosed:
                    return
                env = Envelope.from_wire(raw)
                cid = env.correlation_id
                if cid is not None and cid in self._waiters:
                    waiter = self._waiters.pop(cid)
                    if not waiter.done():
                        waiter.set_result(env)
                    continue
                await self._events.put(env)
        finally:
            await self._events.put(None)


class _suppress:  # noqa: N801 — module-private contextmanager helper
    def __init__(self, *exc_types: type[BaseException]) -> None:
        self._types = exc_types

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> bool:
        return exc_type is not None and issubclass(exc_type, self._types)


__all__ = ["ARCPClient"]
