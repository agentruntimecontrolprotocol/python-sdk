"""Conformance harness — assert load-bearing symbols and constants exist."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    ("module", "symbols"),
    [
        (
            "arcp",
            [
                "PROTOCOL_VERSION",
                "IMPL_VERSION",
                "V1_1_FEATURES",
                "intersect_features",
                "Envelope",
                "Transport",
                "TransportClosed",
                "MemoryTransport",
                "pair_memory_transports",
                "StdioTransport",
                "WebSocketTransport",
                "serve_websocket",
                "ARCPError",
                "ERROR_CODES",
                "PermissionDeniedError",
                "LeaseExpiredError",
                "BudgetExhaustedError",
                "AgentVersionNotAvailableError",
                "HeartbeatLostError",
                "InvalidRequestError",
                "UnauthenticatedError",
                "Lease",
                "LeaseConstraints",
                "ClientInfo",
                "RuntimeInfo",
                "Capabilities",
                "ListJobsFilter",
                "SessionResume",
                "SessionWelcomePayload",
                "parse_agent_ref",
                "parse_budget_amount",
            ],
        ),
        (
            "arcp.client",
            ["ARCPClient", "JobHandle", "JobSubscription", "AutoAckOptions"],
        ),
        (
            "arcp.runtime",
            [
                "ARCPRuntime",
                "JobContext",
                "Agent",
                "ResultStream",
                "SessionContext",
                "BearerVerifier",
                "StaticBearerVerifier",
                "JWTVerifier",
                "EventLog",
                "InMemoryEventLog",
                "SqliteEventLog",
                "validate_lease_shape",
                "validate_lease_op",
                "validate_lease_constraints",
                "is_lease_subset",
                "assert_lease_subset",
            ],
        ),
        ("arcp.middleware.asgi", ["arcp_asgi_app"]),
        ("arcp.middleware.aiohttp", ["arcp_aiohttp_handler", "serve_arcp_aiohttp"]),
        ("arcp.middleware.otel", ["with_tracing", "OTEL_EXTENSION_KEY"]),
    ],
)
def test_public_symbols_exist(module: str, symbols: list[str]) -> None:
    mod = importlib.import_module(module)
    for sym in symbols:
        assert hasattr(mod, sym), f"{module} missing symbol: {sym}"


def test_protocol_version_is_1() -> None:
    import arcp

    assert arcp.PROTOCOL_VERSION == "1"


def test_v1_1_features_complete() -> None:
    import arcp

    expected = {
        "heartbeat",
        "ack",
        "list_jobs",
        "subscribe",
        "lease_expires_at",
        "cost.budget",
        "progress",
        "result_chunk",
        "agent_versions",
    }
    assert set(arcp.V1_1_FEATURES) == expected


def test_error_codes_count_is_15() -> None:
    import arcp

    assert len(arcp.ERROR_CODES) == 15
