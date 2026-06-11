"""ARCPRuntime: accept transports, dispatch envelopes, manage jobs and subscribers."""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Self

from .._auth.bearer import BearerVerifier, Identity
from .._envelope import Envelope
from .._errors import (
    AgentNotAvailableError,
    AgentVersionNotAvailableError,
    InvalidRequestError,
)
from .._logger import get_logger
from .._messages.execution import (
    parse_agent_ref,
)
from .._messages.session import (
    AgentInventoryEntry,
    Capabilities,
    RuntimeInfo,
)
from .._store.eventlog import EventLog, InMemoryEventLog
from .._store.idempotency import IdempotencyStore
from .._transport.base import Transport
from .._version import PROVISIONED_CREDENTIAL_FEATURES, features_for_runtime
from .credentials import CredentialProvisioner, RevocationLog
from .job import Agent, Job
from .lease import (
    LeaseOpContext,
    assert_lease_subset,
    validate_lease_op,
)
from .session import (
    SessionContext,
)

_LOG = get_logger("arcp.runtime.server")


JobAuthorizationPolicy = Callable[["AuthorizationContext"], bool]


@dataclass(frozen=True)
class AuthorizationContext:
    """Inputs to the per-job authorization policy used by `list_jobs` and `subscribe`."""

    requester_principal: str
    job: Job
    operation: str  # "list" | "subscribe" | "cancel"


def _default_authz_policy(ctx: AuthorizationContext) -> bool:
    """Same-principal default: requester must own the job (§14)."""
    return ctx.job.submitter_principal == ctx.requester_principal


@dataclass
class _AgentRegistration:
    name: str
    versions: dict[str, Agent] = field(default_factory=dict)  # pyright: ignore[reportUnknownVariableType]
    default_version: str | None = None
    bare: Agent | None = None  # registered without a version


@dataclass(frozen=True)
class _ResumeRecord:
    """Server-side bookkeeping for a recently-disconnected session.

    Holds the minimum needed to authorize a resume hello and pick the
    event_seq replay point: principal, the secret resume_token, the last
    event_seq the runtime stamped on this session, and an absolute expiry.
    """

    session_id: str
    principal: str
    resume_token: str
    last_event_seq: int
    expires_at: float
    negotiated_features: tuple[str, ...]
    heartbeat_interval_sec: int | None


class ARCPRuntime:
    """Server-side runtime: register agents, accept transports, dispatch envelopes.

    Construct once per process. Wire it to a transport via `await
    runtime.accept(transport)` (typically wrapped by `serve_websocket` or
    the ASGI adapter). Each `accept()` call drives one full session.

    Args:
        runtime: Identifies this runtime (name + version) — echoed in
            every `session.welcome`.
        bearer: Verifies the bearer token in `session.hello.auth`.
            Use `StaticBearerVerifier` for demos, `JWTVerifier` for prod.
        capabilities: Optional override of advertised capabilities;
            defaults to the v1.1 feature set, optionally augmented with
            provisioned-credential features if a `credential_provisioner`
            is configured.
        heartbeat_interval_sec: Server-driven ping interval. `None`
            disables heartbeat. Heartbeat loss tears the session down.
        resume_window_sec: How long to retain a resume record after
            disconnect. `0` disables resume entirely.
        idempotency_ttl_sec: TTL for entries in the idempotency store.
        max_concurrent_jobs: Cap on simultaneous running agent tasks.
        chunk_size_cap: Per-`result_chunk` size cap (spec §14 SHOULD).
        lease_expiry_grace_sec: Bounded grace window (§14) added to
            `expires_at` enforcement to absorb small clock skew.
        job_authorization_policy: Hook controlling list/subscribe/cancel
            visibility (defaults to same-principal).
        event_log: Storage for replayable envelopes. Defaults to
            `InMemoryEventLog`; pass `SqliteEventLog(path)` for durability.
        credential_provisioner: Optional adapter that issues per-job
            credentials. Requires `revocation_log` to also be supplied.
        revocation_log: Durable revocation record for provisioned creds.
        logger: Optional structlog-style logger (defaults to package logger).

    Raises:
        InvalidRequestError: If `credential_provisioner` is supplied
            without a `revocation_log`.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        runtime: RuntimeInfo,
        bearer: BearerVerifier,
        capabilities: Capabilities | None = None,
        heartbeat_interval_sec: int | None = 30,
        resume_window_sec: int = 600,
        idempotency_ttl_sec: float = 24 * 60 * 60,
        max_concurrent_jobs: int = 100,
        chunk_size_cap: int = 1024 * 1024,
        lease_expiry_grace_sec: float = 1.0,
        job_authorization_policy: JobAuthorizationPolicy | None = None,
        event_log: EventLog | None = None,
        credential_provisioner: CredentialProvisioner | None = None,
        revocation_log: RevocationLog | None = None,
        logger: Any = None,
    ) -> None:
        # PLR0913: every arg is an optional, keyword-only configuration knob.
        # Grouping into a config dataclass is a breaking change with no
        # clarity gain. TODO(arcp/v2): revisit on a major-version bump.
        self.runtime_info = runtime
        self.bearer = bearer
        if credential_provisioner is not None and revocation_log is None:
            raise InvalidRequestError(
                "provisioned_credentials requires a revocation_log for durable revocation"
            )
        self.credential_provisioner = credential_provisioner
        self.revocation_log = revocation_log
        self.capabilities = _normalize_capabilities(
            capabilities,
            provisioner_configured=credential_provisioner is not None,
        )
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.resume_window_sec = resume_window_sec
        self.max_concurrent_jobs = max_concurrent_jobs
        self.chunk_size_cap = chunk_size_cap
        self.lease_expiry_grace_sec = lease_expiry_grace_sec
        self.idempotency = IdempotencyStore(ttl_sec=idempotency_ttl_sec)
        self.event_log: EventLog = event_log if event_log is not None else InMemoryEventLog()
        self.policy = job_authorization_policy or _default_authz_policy
        self.logger = logger or _LOG

        self._agents: dict[str, _AgentRegistration] = {}
        self._sessions: dict[str, SessionContext] = {}
        self._resume_records: dict[str, _ResumeRecord] = {}
        # Continued event_seq per session while it has no live connection, so
        # events emitted during the disconnect window keep stamping forward and
        # a resumed session picks up where they left off (#81).
        self._detached_seq: dict[str, int] = {}
        self._jobs: dict[str, Job] = {}
        self._job_tasks: dict[str, asyncio.Task[Any]] = {}
        self._closed = asyncio.Event()
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)

    def register_agent(self, name: str, fn: Agent) -> Self:
        """Register an unversioned agent callable for `name`.

        The callable must match `async def fn(input, ctx: JobContext) -> Any`.
        Returns `self` for chaining.
        """
        reg = self._agents.setdefault(name, _AgentRegistration(name=name))
        reg.bare = fn
        return self

    def register_agent_version(self, name: str, version: str, fn: Agent) -> Self:
        """Register a specific `version` of agent `name`.

        The first version registered becomes the default; override later
        with `set_default_agent_version`. Returns `self` for chaining.
        """
        reg = self._agents.setdefault(name, _AgentRegistration(name=name))
        reg.versions[version] = fn
        if reg.default_version is None:
            reg.default_version = version
        return self

    def set_default_agent_version(self, name: str, version: str) -> Self:
        """Choose which previously-registered `version` is selected when
        a client submits with a bare `name` (no `@version` suffix).

        Raises:
            AgentVersionNotAvailableError: If `name@version` is not registered.
        """
        reg = self._agents.get(name)
        if reg is None or version not in reg.versions:
            raise AgentVersionNotAvailableError(f"unknown agent version: {name}@{version}")
        reg.default_version = version
        return self

    def agent_inventory(self) -> tuple[AgentInventoryEntry, ...]:
        """Snapshot of registered agents for `session.welcome.capabilities.agents`."""
        out: list[AgentInventoryEntry] = []
        for reg in self._agents.values():
            out.append(
                AgentInventoryEntry(
                    name=reg.name,
                    versions=tuple(reg.versions.keys()),
                    default=reg.default_version,
                )
            )
        return tuple(out)

    def _resolve_agent(self, agent_ref: str) -> tuple[Agent, str, str | None]:
        name, version = parse_agent_ref(agent_ref)
        reg = self._agents.get(name)
        if reg is None:
            raise AgentNotAvailableError(f"unknown agent: {name}")
        if version is None:
            if reg.default_version is not None:
                v = reg.default_version
                return reg.versions[v], name, v
            if reg.bare is not None:
                return reg.bare, name, None
            raise AgentNotAvailableError(
                f"agent {name!r} has no default version and no bare registration"
            )
        if version not in reg.versions:
            raise AgentVersionNotAvailableError(f"unknown agent version: {name}@{version}")
        return reg.versions[version], name, version

    async def accept(self, transport: Transport) -> None:
        """Drive one full session over `transport` — handshake, dispatch, teardown.

        Returns when the session ends (peer sends `session.close`, the
        transport closes, heartbeat is lost, or the runtime is closed).
        Spawn one task per inbound connection.
        """
        from ._accept import run_session

        await run_session(self, transport)

    def _record_resume(self, ctx: SessionContext) -> None:
        """Stash a resumable record for `ctx` so a peer may rejoin within the window."""
        if self.resume_window_sec <= 0:
            return
        self._resume_records[ctx.session_id] = _ResumeRecord(
            session_id=ctx.session_id,
            principal=ctx.principal,
            resume_token=ctx.state.resume_token,
            last_event_seq=ctx.latest_event_seq,
            expires_at=time.time() + self.resume_window_sec,
            negotiated_features=ctx.negotiated_features,
            heartbeat_interval_sec=ctx.state.heartbeat_interval_sec,
        )
        # Seed the detached counter so events emitted by surviving jobs during
        # the disconnect window continue stamping past the last live seq (#81).
        self._detached_seq[ctx.session_id] = ctx.latest_event_seq

    def _pop_resumable(self, session_id: str) -> _ResumeRecord | None:
        """Look up and remove an unexpired resume record for `session_id`."""
        self._sweep_resume_records()
        return self._resume_records.pop(session_id, None)

    def _sweep_resume_records(self) -> None:
        now = time.time()
        expired = [sid for sid, rec in self._resume_records.items() if rec.expires_at <= now]
        for sid in expired:
            self._resume_records.pop(sid, None)

    async def _deliver_detached(self, session_id: str, env: Envelope) -> None:
        """Persist a job event emitted while its session has no live connection.

        Stamps the next session-scoped event_seq (continuing past the last seq
        the live session stamped) and appends to the event log so a resume
        replays it without a gap. There is no transport to send to yet.
        """
        if env.type in {"job.event", "job.result", "job.error"} and env.event_seq is None:
            seq = self._detached_seq.get(session_id, 0) + 1
            self._detached_seq[session_id] = seq
            env = env.model_copy(update={"event_seq": seq})
        with contextlib.suppress(Exception):
            await self.event_log.append(session_id, env.to_wire())

    async def _reclaim_expired_event_logs(self) -> None:
        """Drop event-log buffers for sessions whose resume window has elapsed.

        The only other reclamation path is `release_through` (driven by the
        optional `ack` feature); without this, a no-ack workload grows the
        event log without bound (#89). Called on each session teardown.
        """
        now = time.time()
        expired = [sid for sid, rec in self._resume_records.items() if rec.expires_at <= now]
        for sid in expired:
            self._resume_records.pop(sid, None)
            self._detached_seq.pop(sid, None)
            with contextlib.suppress(Exception):
                await self.event_log.drop_session(sid)

    async def _dispatch(self, ctx: SessionContext, env: Envelope) -> None:
        t = env.type
        if t == "session.hello":
            raise InvalidRequestError("session.hello already sent on this connection")
        if t == "session.pong":
            return  # informational only
        spec = self._dispatch_table().get(t)
        if spec is None:
            raise InvalidRequestError(f"unknown envelope type: {t!r}")
        required_feature, handler = spec
        if required_feature is not None:
            self._require_feature(ctx, required_feature)
        result = handler(self, ctx, env)
        if result is not None:
            await result

    @staticmethod
    def _dispatch_table() -> dict[
        str, tuple[str | None, Callable[[ARCPRuntime, SessionContext, Envelope], Any]]
    ]:
        return _DISPATCH_TABLE

    def _require_feature(self, ctx: SessionContext, name: str) -> None:
        if not ctx.has_feature(name):
            raise InvalidRequestError(f"feature {name!r} not negotiated for this session")

    async def _run_job(
        self,
        job: Job,
        agent_fn: Agent,
        agent_input: Any,
        *,
        max_runtime_sec: int | None,
    ) -> None:
        from ._job_runner import run_job

        await run_job(self, job, agent_fn, agent_input, max_runtime_sec=max_runtime_sec)

    async def close(self) -> None:
        """Cancel all running jobs and close the event log.

        Idempotent. Does not close in-flight transports — those are
        owned by the caller of `accept()`. Call after the embedding
        server (e.g. the WebSocket server) has stopped accepting new
        connections.
        """
        self._closed.set()
        for task in list(self._job_tasks.values()):
            if not task.done():
                task.cancel()
        for task in list(self._job_tasks.values()):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        await self.event_log.close()


from . import _handlers  # noqa: E402

_DISPATCH_TABLE: dict[
    str, tuple[str | None, Callable[[ARCPRuntime, SessionContext, Envelope], Any]]
] = {
    "session.close": (None, _handlers.handle_close),
    # Legacy alias for clients still emitting the pre-§6.7 close verb.
    "session.bye": (None, _handlers.handle_close),
    "session.ping": (None, _handlers.handle_ping),
    "session.ack": (None, _handlers.handle_ack),
    "session.list_jobs": ("list_jobs", _handlers.handle_list_jobs),
    "job.submit": (None, _handlers.handle_submit),
    "job.cancel": (None, _handlers.handle_cancel),
    "job.subscribe": ("subscribe", _handlers.handle_subscribe),
    "job.unsubscribe": ("subscribe", _handlers.handle_unsubscribe),
}

__all__ = (
    "ARCPRuntime",
    "AuthorizationContext",
    "Identity",
    "JobAuthorizationPolicy",
    "LeaseOpContext",
    "RuntimeInfo",
    "assert_lease_subset",
    "validate_lease_op",
)


def _normalize_capabilities(
    capabilities: Capabilities | None,
    *,
    provisioner_configured: bool,
) -> Capabilities:
    if capabilities is None:
        return Capabilities(
            encodings=("json",),
            features=features_for_runtime(provisioner_configured=provisioner_configured),
        )
    features = tuple(
        feature
        for feature in capabilities.features
        if provisioner_configured or feature not in PROVISIONED_CREDENTIAL_FEATURES
    )
    if provisioner_configured:
        features = tuple(dict.fromkeys((*features, *PROVISIONED_CREDENTIAL_FEATURES)))
    return capabilities.model_copy(update={"features": features})
