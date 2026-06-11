"""ARCP (Agent Runtime Control Protocol) v1.1 — Python reference SDK."""

from __future__ import annotations

from ._envelope import Envelope
from ._errors import (
    ERROR_CODES,
    AgentNotAvailableError,
    AgentVersionNotAvailableError,
    ARCPCancelledError,
    ARCPError,
    ARCPTimeoutError,
    BudgetExhaustedError,
    DuplicateKeyError,
    HeartbeatLostError,
    InternalError,
    InvalidRequestError,
    JobNotFoundError,
    LeaseExpiredError,
    LeaseSubsetViolationError,
    PermissionDeniedError,
    ResumeWindowExpiredError,
    UnauthenticatedError,
    error_class_for,
    error_from_payload,
)
from ._messages.execution import (
    CredentialConstraintsPayload,
    CredentialPayload,
    Lease,
    LeaseConstraints,
    parse_agent_ref,
    parse_budget_amount,
)
from ._messages.session import (
    Capabilities,
    ClientInfo,
    ListJobsFilter,
    RuntimeInfo,
    SessionResume,
    SessionWelcomePayload,
)
from ._runtime.credentials import Credential, CredentialConstraints
from ._transport.base import Transport, TransportClosed
from ._transport.in_memory import MemoryTransport, pair_memory_transports
from ._transport.stdio import StdioTransport
from ._transport.websocket import WebSocketTransport, serve_websocket
from ._version import IMPL_VERSION, PROTOCOL_VERSION, V1_1_FEATURES, intersect_features

__all__ = (
    "ERROR_CODES",
    "IMPL_VERSION",
    # version
    "PROTOCOL_VERSION",
    "V1_1_FEATURES",
    # errors
    "ARCPCancelledError",
    "ARCPError",
    "ARCPTimeoutError",
    "AgentNotAvailableError",
    "AgentVersionNotAvailableError",
    "BudgetExhaustedError",
    # messages (commonly-used)
    "Capabilities",
    "ClientInfo",
    "Credential",
    "CredentialConstraints",
    "CredentialConstraintsPayload",
    "CredentialPayload",
    "DuplicateKeyError",
    # envelope
    "Envelope",
    "HeartbeatLostError",
    "InternalError",
    "InvalidRequestError",
    "JobNotFoundError",
    "Lease",
    "LeaseConstraints",
    "LeaseExpiredError",
    "LeaseSubsetViolationError",
    "ListJobsFilter",
    "MemoryTransport",
    "PermissionDeniedError",
    "ResumeWindowExpiredError",
    "RuntimeInfo",
    "SessionResume",
    "SessionWelcomePayload",
    "StdioTransport",
    # transports
    "Transport",
    "TransportClosed",
    "UnauthenticatedError",
    "WebSocketTransport",
    "error_class_for",
    "error_from_payload",
    "intersect_features",
    "pair_memory_transports",
    "parse_agent_ref",
    "parse_budget_amount",
    "serve_websocket",
)
