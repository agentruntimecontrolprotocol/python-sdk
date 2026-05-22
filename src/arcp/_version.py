"""Wire and implementation version constants and feature negotiation helper."""

from __future__ import annotations

PROTOCOL_VERSION: str = "1.1"
IMPL_VERSION: str = "1.1.0"

V1_1_FEATURES: tuple[str, ...] = (
    "heartbeat",
    "ack",
    "list_jobs",
    "subscribe",
    "lease_expires_at",
    "cost.budget",
    "progress",
    "result_chunk",
    "agent_versions",
)

PROVISIONED_CREDENTIAL_FEATURES: tuple[str, ...] = (
    "model.use",
    "provisioned_credentials",
)


def features_for_runtime(*, provisioner_configured: bool) -> tuple[str, ...]:
    """Return the runtime's default v1.1 feature set for its credential config."""
    if not provisioner_configured:
        return V1_1_FEATURES
    return V1_1_FEATURES + PROVISIONED_CREDENTIAL_FEATURES


def intersect_features(
    a: tuple[str, ...] | list[str], b: tuple[str, ...] | list[str]
) -> tuple[str, ...]:
    """Return the negotiated feature set: features present in both peers, in `a` order."""
    bset = set(b)
    return tuple(f for f in a if f in bset)


__all__ = (
    "IMPL_VERSION",
    "PROTOCOL_VERSION",
    "PROVISIONED_CREDENTIAL_FEATURES",
    "V1_1_FEATURES",
    "features_for_runtime",
    "intersect_features",
)
