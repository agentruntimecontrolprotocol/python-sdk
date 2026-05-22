"""SessionContext: per-connection state, seq stamping, send queue, subscriber fan-out."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .._envelope import Envelope
from .._errors import HeartbeatLostError
from .._logger import get_logger
from .._transport.base import Transport, TransportClosed
from .._ulid import new_envelope_id, new_resume_token, new_session_id

if TYPE_CHECKING:
    from .._auth.bearer import Identity


_LOG = get_logger("arcp.runtime.session")


@dataclass
class SubscriberLink:
    """Per-subscriber-session fan-out state for one job subscription."""

    subscriber_session: SessionContext
    next_seq: int = 0  # subscriber-scoped event_seq counter (0 = unset; first event uses 1)


@dataclass
class SessionState:
    """Server-side session record."""

    session_id: str
    resume_token: str
    principal: str
    negotiated_features: tuple[str, ...]
    heartbeat_interval_sec: int | None
    resume_window_sec: int
    accepted_at: datetime
    last_acked_seq: int = 0


class SessionContext:
    """Per-connection runtime state and the single emit primitive (seq stamp + enqueue)."""

    def __init__(
        self,
        *,
        transport: Transport,
        state: SessionState,
        send_queue: asyncio.Queue[Envelope | None],
        identity: Identity | None = None,
    ) -> None:
        self.transport = transport
        self.state = state
        self.identity = identity
        self._send_queue = send_queue
        self._event_seq = 0
        self.heartbeat_outcome: asyncio.Future[None] | None = None
        self._last_inbound_at = datetime.now(UTC)
        # job_id -> {subscriber_session_id: SubscriberLink}
        self.subscribers: dict[str, dict[str, SubscriberLink]] = {}

    @property
    def session_id(self) -> str:
        return self.state.session_id

    @property
    def principal(self) -> str:
        return self.state.principal

    @property
    def negotiated_features(self) -> tuple[str, ...]:
        return self.state.negotiated_features

    def has_feature(self, name: str) -> bool:
        return name in self.state.negotiated_features

    def next_event_seq(self) -> int:
        """Non-coroutine: bump and return the session-scoped event_seq counter."""
        self._event_seq += 1
        return self._event_seq

    @property
    def latest_event_seq(self) -> int:
        return self._event_seq

    def set_event_seq(self, value: int) -> None:
        """Used during resume replay so live emissions continue after the replay tail."""
        self._event_seq = value

    def record_inbound(self) -> None:
        self._last_inbound_at = datetime.now(UTC)

    @property
    def last_inbound_at(self) -> datetime:
        return self._last_inbound_at

    def record_ack(self, last_processed_seq: int) -> None:
        self.state.last_acked_seq = max(self.state.last_acked_seq, last_processed_seq)

    def stamp_and_enqueue(self, env: Envelope) -> None:
        """Single non-await primitive: bump seq if needed, enqueue for the write pump."""
        if env.type in {"job.event", "job.result", "job.error"} and env.event_seq is None:
            env = env.model_copy(update={"event_seq": self.next_event_seq()})
        self._send_queue.put_nowait(env)

    async def send(self, env: Envelope) -> None:
        """Enqueue a single envelope for the write pump and fan it out to subscribers."""
        self.stamp_and_enqueue(env)
        if env.type in {"job.event", "job.result", "job.error"} and env.job_id:
            await self._fanout_to_subscribers(env)

    async def _fanout_to_subscribers(self, env: Envelope) -> None:
        subs = self.subscribers.get(env.job_id or "")
        if not subs:
            return
        for link in list(subs.values()):
            sub = link.subscriber_session
            link.next_seq += 1
            payload = _redact_subscriber_payload(env.payload)
            forward = env.model_copy(
                update={
                    "id": new_envelope_id(),
                    "session_id": sub.session_id,
                    "event_seq": link.next_seq,
                    "payload": payload,
                }
            )
            sub.stamp_and_enqueue(forward)

    def add_subscriber(self, job_id: str, subscriber: SessionContext) -> SubscriberLink:
        subs = self.subscribers.setdefault(job_id, {})
        link = subs.get(subscriber.session_id)
        if link is None:
            link = SubscriberLink(subscriber_session=subscriber)
            subs[subscriber.session_id] = link
        return link

    def remove_subscriber(self, job_id: str, subscriber_session_id: str) -> None:
        subs = self.subscribers.get(job_id)
        if not subs:
            return
        subs.pop(subscriber_session_id, None)
        if not subs:
            self.subscribers.pop(job_id, None)


def make_session_state(  # noqa: PLR0913
    *,
    principal: str,
    negotiated_features: tuple[str, ...],
    heartbeat_interval_sec: int | None,
    resume_window_sec: int,
    session_id: str | None = None,
    resume_token: str | None = None,
) -> SessionState:
    # PLR0913: internal factory; every kwarg maps onto a `SessionState` field
    # with no opportunity to group meaningfully (mixed concerns: identity,
    # negotiation, lifecycle).
    return SessionState(
        session_id=session_id or new_session_id(),
        resume_token=resume_token or new_resume_token(),
        principal=principal,
        negotiated_features=negotiated_features,
        heartbeat_interval_sec=heartbeat_interval_sec,
        resume_window_sec=resume_window_sec,
        accepted_at=datetime.now(UTC),
    )


def _redact_subscriber_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if (
        payload.get("kind") != "status"
        or not isinstance(payload.get("body"), dict)
        or payload["body"].get("phase") != "credential_rotated"
    ):
        return payload
    body = dict(payload["body"])
    body.pop("value", None)
    return {**payload, "body": body}


async def write_pump(transport: Transport, queue: asyncio.Queue[Envelope | None]) -> None:
    """Drain `queue` to `transport.send`. Sentinel `None` exits cleanly."""
    while True:
        item = await queue.get()
        if item is None:
            return
        try:
            await transport.send(item.to_wire())
        except TransportClosed:
            return


async def heartbeat_loop(
    ctx: SessionContext,
    *,
    interval: float,
    miss_threshold: int = 2,
    on_ping: Any = None,
) -> None:
    """Send `session.ping` on each interval; raise `HeartbeatLostError` after miss_threshold."""
    from .._messages.session import SessionPingPayload
    from .._ulid import new_ulid

    last_seen = ctx.last_inbound_at
    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return
        now = datetime.now(UTC)
        gap = (now - ctx.last_inbound_at).total_seconds()
        if gap >= interval * miss_threshold:
            if ctx.heartbeat_outcome is not None and not ctx.heartbeat_outcome.done():
                ctx.heartbeat_outcome.set_exception(HeartbeatLostError("heartbeat lost"))
            _LOG.warning("heartbeat_lost", session_id=ctx.session_id, gap=gap)
            return
        nonce = new_ulid()
        payload = SessionPingPayload(nonce=nonce, sent_at=now.isoformat()).model_dump(mode="json")
        env = Envelope(
            id=new_envelope_id(),
            type="session.ping",
            session_id=ctx.session_id,
            payload=payload,
        )
        ctx.stamp_and_enqueue(env)
        if on_ping is not None:
            on_ping(nonce)
        _ = last_seen  # symbol-keep


__all__ = (
    "SessionContext",
    "SessionState",
    "SubscriberLink",
    "heartbeat_loop",
    "make_session_state",
    "write_pump",
)
