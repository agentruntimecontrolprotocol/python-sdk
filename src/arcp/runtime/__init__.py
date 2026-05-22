"""Public runtime surface."""

from __future__ import annotations

from .._auth.bearer import BearerVerifier, Identity, StaticBearerVerifier
from .._auth.jwt import JWTVerifier
from .._runtime.credentials import (
    Credential,
    CredentialConstraints,
    CredentialProvisioner,
    InMemoryCredentialProvisioner,
    InMemoryRevocationLog,
    JobCredentialContext,
    RevocationLog,
    UpstreamBudgetExhausted,
)
from .._runtime.job import Agent, Job, JobContext, ResultStream
from .._runtime.lease import (
    LeaseOpContext,
    assert_lease_subset,
    initial_budget_from_lease,
    is_lease_subset,
    validate_lease_constraints,
    validate_lease_op,
    validate_lease_shape,
)
from .._runtime.server import (
    ARCPRuntime,
    AuthorizationContext,
    JobAuthorizationPolicy,
)
from .._runtime.session import SessionContext, SessionState
from .._store.eventlog import EventLog, InMemoryEventLog, SqliteEventLog
from .._version import features_for_runtime

__all__ = (
    "ARCPRuntime",
    "Agent",
    "AuthorizationContext",
    "BearerVerifier",
    "Credential",
    "CredentialConstraints",
    "CredentialProvisioner",
    "EventLog",
    "Identity",
    "InMemoryCredentialProvisioner",
    "InMemoryEventLog",
    "InMemoryRevocationLog",
    "JWTVerifier",
    "Job",
    "JobAuthorizationPolicy",
    "JobContext",
    "JobCredentialContext",
    "LeaseOpContext",
    "ResultStream",
    "RevocationLog",
    "SessionContext",
    "SessionState",
    "SqliteEventLog",
    "StaticBearerVerifier",
    "UpstreamBudgetExhausted",
    "assert_lease_subset",
    "features_for_runtime",
    "initial_budget_from_lease",
    "is_lease_subset",
    "validate_lease_constraints",
    "validate_lease_op",
    "validate_lease_shape",
)
