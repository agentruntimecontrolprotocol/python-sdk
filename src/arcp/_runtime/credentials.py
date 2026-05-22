"""Provisioned credential interfaces and in-memory test doubles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .._messages.execution import Lease, LeaseConstraints


@dataclass(frozen=True)
class CredentialConstraints:
    """Constraints baked into an upstream credential."""

    cost_budget: tuple[str, ...] = ()
    model_use: tuple[str, ...] = ()
    expires_at: str | None = None


@dataclass(frozen=True)
class Credential:
    """Lease-bound credential returned to the submitting client."""

    id: str
    scheme: str
    value: str
    endpoint: str
    profile: str | None = None
    constraints: CredentialConstraints | None = None


@dataclass(frozen=True)
class JobCredentialContext:
    """Context supplied to a provisioner when a job is accepted."""

    job_id: str
    agent: str
    agent_version: str | None
    submitter_principal: str
    parent_job_id: str | None
    lease: Lease
    lease_constraints: LeaseConstraints | None


class UpstreamBudgetExhausted(Exception):
    """Raised by an upstream gateway adapter when its budget backstop rejects a call."""


@runtime_checkable
class RevocationLog(Protocol):
    """Durable record of credentials that still need revocation."""

    async def record(self, job_id: str, credential_id: str) -> None: ...
    async def forget(self, job_id: str, credential_id: str) -> None: ...
    async def outstanding(self) -> tuple[tuple[str, str], ...]: ...


@runtime_checkable
class CredentialProvisioner(Protocol):
    """Vendor-neutral hook for issuing and revoking lease-bound credentials."""

    async def issue(
        self,
        lease: Lease,
        ctx: JobCredentialContext,
    ) -> tuple[Credential, ...]: ...

    async def revoke(self, credential_id: str) -> None: ...


class InMemoryRevocationLog:
    """Single-process revocation log for tests and local examples."""

    def __init__(self) -> None:
        self._outstanding: set[tuple[str, str]] = set()

    async def record(self, job_id: str, credential_id: str) -> None:
        self._outstanding.add((job_id, credential_id))

    async def forget(self, job_id: str, credential_id: str) -> None:
        self._outstanding.discard((job_id, credential_id))

    async def outstanding(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._outstanding))


class InMemoryCredentialProvisioner:
    """Deterministic provisioner test double; never makes network calls."""

    def __init__(
        self,
        *,
        factory: Callable[[Lease, JobCredentialContext], tuple[Credential, ...]] | None = None,
    ) -> None:
        self._factory = factory or self._default_factory
        self._issued: list[Credential] = []
        self._revoked: list[str] = []

    async def issue(self, lease: Lease, ctx: JobCredentialContext) -> tuple[Credential, ...]:
        creds = self._factory(lease, ctx)
        self._issued.extend(creds)
        return creds

    async def revoke(self, credential_id: str) -> None:
        self._revoked.append(credential_id)

    @property
    def issued(self) -> tuple[Credential, ...]:
        return tuple(self._issued)

    @property
    def revoked(self) -> tuple[str, ...]:
        return tuple(self._revoked)

    @staticmethod
    def _default_factory(lease: Lease, ctx: JobCredentialContext) -> tuple[Credential, ...]:
        constraints = CredentialConstraints(
            cost_budget=tuple(lease.get("cost.budget", ())),
            model_use=tuple(lease.get("model.use", ())),
            expires_at=ctx.lease_constraints.expires_at if ctx.lease_constraints else None,
        )
        return (
            Credential(
                id=f"cred_{ctx.job_id}",
                scheme="bearer",
                value=f"test-token-{ctx.job_id}",
                endpoint="https://gateway.example.test/v1",
                profile="test",
                constraints=constraints,
            ),
        )


__all__ = (
    "Credential",
    "CredentialConstraints",
    "CredentialProvisioner",
    "InMemoryCredentialProvisioner",
    "InMemoryRevocationLog",
    "JobCredentialContext",
    "RevocationLog",
    "UpstreamBudgetExhausted",
)
