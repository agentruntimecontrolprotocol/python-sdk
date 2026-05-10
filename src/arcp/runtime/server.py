"""Top-level ARCP runtime server (RFC §5, §6.3).

The :class:`ARCPRuntime` accepts inbound transports (one per session),
drives the handshake, and dispatches subsequent envelopes to type-specific
handlers. The dispatch table is populated incrementally across phases:

* Phase 2 (here): handshake, ping/pong, session.close, unknown-message
  handling per §21.3.
* Phase 3: tool.invoke / job lifecycle / cancellation / interrupts.
* Phase 4: human-in-the-loop and permission/lease handling.
* Phase 5: subscriptions, artifacts, resume.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

from arcp.envelope import Envelope
from arcp.errors import ARCPError, ErrorCode
from arcp.extensions import classify_unknown
from arcp.messages import validate_payload
from arcp.messages.control import (
    CancelAcceptedPayload,
    CancelPayload,
    CancelRefusedPayload,
)
from arcp.messages.execution import ToolInvokePayload
from arcp.messages.session import (
    Capabilities,
    RuntimeIdentity,
    SessionUnauthenticatedPayload,
)
from arcp.runtime.job import JobManager
from arcp.runtime.session import HandshakeDriver, SessionPhase, SessionState
from arcp.runtime.stream import StreamManager
from arcp.store.eventlog import EventLog
from arcp.transport.base import Transport, TransportClosed

logger = structlog.get_logger("arcp.runtime")

DispatchHandler = Callable[["ARCPRuntime", SessionState, Envelope], Awaitable[None]]


@dataclass
class RuntimeConfig:
    runtime_identity: RuntimeIdentity
    advertised_capabilities: Capabilities
    bearer_validator: Any | None = None
    jwt_validator: Any | None = None
    event_log_path: str = ":memory:"
    session_lifetime_seconds: int = 3600
    # Internal heartbeat-watchdog interval (seconds). Overrides
    # ``advertised_capabilities.heartbeat_interval_seconds`` for testing where
    # 30-second intervals are impractical. Use an int that floors at 1 in
    # production; tests may pass a float via :attr:`heartbeat_interval_override`.
    heartbeat_interval_override: float | None = None
    heartbeat_miss_threshold: int = 2


ToolImpl = Callable[[Any, dict[str, Any]], Awaitable[Any]]


@dataclass
class ARCPRuntime:
    """Server-side ARCP runtime."""

    config: RuntimeConfig
    _event_log: EventLog | None = None
    _handshake: HandshakeDriver | None = None
    _sessions: dict[str, SessionState] = field(default_factory=dict[str, SessionState])
    _dispatch: dict[str, DispatchHandler] = field(default_factory=dict[str, DispatchHandler])
    _tools: dict[str, ToolImpl] = field(default_factory=dict[str, ToolImpl])
    _job_managers: dict[str, JobManager] = field(default_factory=dict[str, JobManager])
    _stream_managers: dict[str, StreamManager] = field(
        default_factory=dict[str, StreamManager]
    )
    _started: bool = False

    def register_tool(self, name: str, impl: ToolImpl) -> None:
        """Register an async tool implementation by name."""

        self._tools[name] = impl

    def get_job_manager(self, session_id: str) -> JobManager:
        manager = self._job_managers.get(session_id)
        if manager is None:
            raise RuntimeError(f"no job manager bound for session {session_id!r}")
        return manager

    async def start(self) -> None:
        if self._started:
            return
        self._event_log = EventLog(self.config.event_log_path)
        await self._event_log.open()
        self._handshake = HandshakeDriver(
            runtime_identity=self.config.runtime_identity,
            advertised=self.config.advertised_capabilities,
            bearer_validator=self.config.bearer_validator,
            jwt_validator=self.config.jwt_validator,
            session_lifetime_seconds=self.config.session_lifetime_seconds,
        )
        self._register_default_handlers()
        self._started = True

    async def close(self) -> None:
        if self._event_log is not None:
            await self._event_log.close()
        self._started = False

    @property
    def event_log(self) -> EventLog:
        if self._event_log is None:
            raise RuntimeError("ARCPRuntime not started")
        return self._event_log

    def register_handler(self, message_type: str, handler: DispatchHandler) -> None:
        """Register a dispatch handler for a message type. Idempotent overwrite."""

        self._dispatch[message_type] = handler

    def _register_default_handlers(self) -> None:
        async def _handle_ping(
            rt: ARCPRuntime, state: SessionState, env: Envelope
        ) -> None:
            response = Envelope(
                id=_new_msg_id(),
                type="pong",
                session_id=state.session_id,
                correlation_id=env.id,
                payload={"nonce": env.payload.get("nonce")},
            )
            await rt._send(state, response)

        async def _handle_close(
            rt: ARCPRuntime, state: SessionState, env: Envelope
        ) -> None:
            state.phase = SessionPhase.CLOSED
            await rt.event_log.append(env)

        async def _handle_tool_invoke(
            rt: ARCPRuntime, state: SessionState, env: Envelope
        ) -> None:
            payload = ToolInvokePayload.model_validate(env.payload)
            impl = rt._tools.get(payload.tool)
            if impl is None:
                raise ARCPError(
                    ErrorCode.NOT_FOUND, f"tool {payload.tool!r} is not registered"
                )
            manager = rt._job_managers[state.session_id]
            await manager.submit(
                session_id=state.session_id,
                tool_name=payload.tool,
                arguments=dict(payload.arguments),
                impl=impl,
                correlation_id=env.id,
                trace_id=env.trace_id,
            )

        async def _handle_cancel(
            rt: ARCPRuntime, state: SessionState, env: Envelope
        ) -> None:
            payload = CancelPayload.model_validate(env.payload)
            manager = rt._job_managers[state.session_id]
            try:
                if payload.target == "job":
                    await manager.cancel(
                        payload.target_id, deadline_ms=payload.deadline_ms
                    )
                    accepted = Envelope(
                        id=_new_msg_id(),
                        type="cancel.accepted",
                        session_id=state.session_id,
                        correlation_id=env.id,
                        payload=CancelAcceptedPayload(
                            target=payload.target, target_id=payload.target_id
                        ).model_dump(),
                    )
                    await rt._send(state, accepted)
                else:
                    raise ARCPError(
                        ErrorCode.UNIMPLEMENTED,
                        f"cancel target {payload.target!r} not supported in v0.1",
                    )
            except ARCPError as exc:
                refused = Envelope(
                    id=_new_msg_id(),
                    type="cancel.refused",
                    session_id=state.session_id,
                    correlation_id=env.id,
                    payload=CancelRefusedPayload(
                        target=payload.target,
                        target_id=payload.target_id,
                        code=str(exc.code),
                        message=exc.message,
                    ).model_dump(),
                )
                await rt._send(state, refused)

        self.register_handler("ping", _handle_ping)
        self.register_handler("session.close", _handle_close)
        self.register_handler("tool.invoke", _handle_tool_invoke)
        self.register_handler("cancel", _handle_cancel)

    async def serve_session(self, transport: Transport) -> None:
        """Drive a full session over ``transport`` until close.

        The runtime handles handshake → dispatch → graceful close. Callers
        create one transport per session; for WebSocket this is one socket
        per accepted connection.
        """

        if not self._started:
            await self.start()
        assert self._handshake is not None

        state: SessionState | None = None
        try:
            while True:
                try:
                    raw = await transport.recv()
                except TransportClosed:
                    return

                try:
                    envelope = Envelope.from_wire(raw)
                except Exception as exc:
                    await self._send_raw(
                        transport,
                        Envelope(
                            id=_new_msg_id(),
                            type="nack",
                            payload={
                                "code": str(ErrorCode.INVALID_ARGUMENT),
                                "message": f"unparseable envelope: {exc}",
                            },
                        ),
                    )
                    continue

                if state is None:
                    state = await self._drive_handshake(transport, envelope)
                    continue

                await self._dispatch_envelope(transport, state, envelope)

                if state.phase in (SessionPhase.CLOSED, SessionPhase.EVICTED):
                    return
        finally:
            with contextlib_suppress(Exception):
                await transport.close()

    async def _drive_handshake(
        self, transport: Transport, envelope: Envelope
    ) -> SessionState | None:
        assert self._handshake is not None
        if envelope.type != "session.open":
            unauth = Envelope(
                id=_new_msg_id(),
                type="session.unauthenticated",
                correlation_id=envelope.id,
                payload=SessionUnauthenticatedPayload(
                    code=str(ErrorCode.UNAUTHENTICATED),
                    message=f"first message must be session.open, got {envelope.type!r}",
                ).model_dump(),
            )
            logger.warning(
                "pre-acceptance message dropped", message_type=envelope.type, message_id=envelope.id
            )
            await self._send_raw(transport, unauth)
            return None

        result = self._handshake.handle_open(envelope)
        await self._send_raw(transport, result.response)
        if result.state is None:
            return None
        self._sessions[result.state.session_id] = result.state
        self._bind_transport(result.state.session_id, transport)
        streams = StreamManager()
        self._stream_managers[result.state.session_id] = streams
        bound_state = result.state

        async def _sink(env: Envelope) -> None:
            await self._send(bound_state, env)

        hb_interval: float = (
            self.config.heartbeat_interval_override
            if self.config.heartbeat_interval_override is not None
            else float(self.config.advertised_capabilities.heartbeat_interval_seconds)
        )
        self._job_managers[result.state.session_id] = JobManager(
            sink=_sink,
            streams=streams,
            heartbeat_interval_seconds=hb_interval,
            heartbeat_recovery=self.config.advertised_capabilities.heartbeat_recovery,
            miss_threshold=self.config.heartbeat_miss_threshold,
        )
        await self.event_log.append(envelope)
        await self.event_log.append(result.response)
        return result.state

    async def _dispatch_envelope(
        self, transport: Transport, state: SessionState, envelope: Envelope
    ) -> None:
        # Persist inbound for dedupe & resume.
        was_new = await self.event_log.append(envelope)
        if not was_new:
            logger.info(
                "duplicate envelope deduped",
                session_id=state.session_id,
                message_id=envelope.id,
            )
            return

        # Validate payload against registered model when one exists.
        try:
            validated = validate_payload(envelope.type, envelope.payload)
        except Exception as exc:
            await self._nack(state, envelope, ErrorCode.INVALID_ARGUMENT, str(exc))
            return
        del validated

        handler = self._dispatch.get(envelope.type)
        if handler is not None:
            try:
                await handler(self, state, envelope)
            except ARCPError as exc:
                await self._nack(state, envelope, exc.code, exc.message)
            return

        # Unknown type per §21.3.
        decision = classify_unknown(envelope, state.extensions)
        if decision.action == "drop":
            logger.debug(
                "dropping optional unadvertised extension",
                session_id=state.session_id,
                message_type=envelope.type,
            )
            return
        await self._nack(state, envelope, ErrorCode.UNIMPLEMENTED, decision.reason)

    async def _send(self, state: SessionState, envelope: Envelope) -> None:
        """Persist + forward via the session's bound transport.

        v0.1 keeps the transport reference on the active dispatch frame,
        so this helper is a no-op until the transport mapping is wired
        in subsequent phases. Logging-only here lets handlers be written
        in the right shape ahead of time.
        """

        await self.event_log.append(envelope)
        transport = self._transports.get(state.session_id)
        if transport is not None:
            await self._send_raw(transport, envelope)

    async def _send_raw(self, transport: Transport, envelope: Envelope) -> None:
        await transport.send(envelope.to_wire())

    async def _nack(
        self,
        state: SessionState,
        envelope: Envelope,
        code: ErrorCode,
        message: str,
    ) -> None:
        nack = Envelope(
            id=_new_msg_id(),
            type="nack",
            session_id=state.session_id,
            correlation_id=envelope.id,
            payload={"code": str(code), "message": message},
        )
        await self._send(state, nack)

    @property
    def _transports(self) -> dict[str, Transport]:
        if not hasattr(self, "_transport_table"):
            self._transport_table: dict[str, Transport] = {}
        return self._transport_table

    def _bind_transport(self, session_id: str, transport: Transport) -> None:
        self._transports[session_id] = transport


def _new_msg_id() -> str:
    return f"msg_{uuid.uuid4().hex[:12]}"


# Lightweight contextlib.suppress avoiding import cycle clutter.
class contextlib_suppress:  # noqa: N801 - module-private helper
    def __init__(self, *exc_types: type[BaseException]) -> None:
        self._types = exc_types

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: object) -> bool:
        return exc_type is not None and issubclass(exc_type, self._types)


__all__ = ["ARCPRuntime", "RuntimeConfig"]
