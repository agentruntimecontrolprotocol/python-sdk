"""ARCPRuntime: accept transports, dispatch envelopes, manage jobs and subscribers."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
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


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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
    versions: dict[str, Agent] = field(default_factory=dict)
    default_version: str | None = None
    bare: Agent | None = None  # registered without a version


class ARCPRuntime:
    """Server-side runtime: register agents, accept transports, dispatch envelopes."""

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
        self.idempotency = IdempotencyStore(ttl_sec=idempotency_ttl_sec)
        self.event_log: EventLog = event_log if event_log is not None else InMemoryEventLog()
        self.policy = job_authorization_policy or _default_authz_policy
        self.logger = logger or _LOG

        self._agents: dict[str, _AgentRegistration] = {}
        self._sessions: dict[str, SessionContext] = {}
        self._jobs: dict[str, Job] = {}
        self._job_tasks: dict[str, asyncio.Task[Any]] = {}
        self._closed = asyncio.Event()
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)

    def register_agent(self, name: str, fn: Agent) -> Self:
        reg = self._agents.setdefault(name, _AgentRegistration(name=name))
        reg.bare = fn
        return self

    def register_agent_version(self, name: str, version: str, fn: Agent) -> Self:
        reg = self._agents.setdefault(name, _AgentRegistration(name=name))
        reg.versions[version] = fn
        if reg.default_version is None:
            reg.default_version = version
        return self

    def set_default_agent_version(self, name: str, version: str) -> Self:
        reg = self._agents.get(name)
        if reg is None or version not in reg.versions:
            raise AgentVersionNotAvailableError(f"unknown agent version: {name}@{version}")
        reg.default_version = version
        return self

    def agent_inventory(self) -> tuple[AgentInventoryEntry, ...]:
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
        """Drive one full session over `transport`. Returns when session ends."""
        from ._accept import run_session

        await run_session(self, transport)

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
    "session.bye": (None, _handlers.handle_bye),
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
