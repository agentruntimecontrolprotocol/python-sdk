"""#84 / #85 — segment-anchored glob matching and sound subset containment."""

from __future__ import annotations

import pytest

from arcp._errors import PermissionDeniedError
from arcp._runtime.lease import (
    LeaseOpContext,
    canonicalize_target,
    is_lease_subset,
    validate_lease_op,
)


def _allows(lease: dict, capability: str, target: str) -> bool:
    try:
        validate_lease_op(lease, LeaseOpContext(capability=capability, target=target))
        return True
    except PermissionDeniedError:
        return False


# ---- #84: single `*` does not cross `/`; `**` does ------------------------


def test_single_star_does_not_match_across_separator() -> None:
    lease = {"fs.read": ["/ws/*"]}
    assert _allows(lease, "fs.read", "/ws/a") is True
    assert _allows(lease, "fs.read", "/ws/a/b") is False


def test_globstar_matches_across_separator() -> None:
    lease = {"fs.read": ["/ws/**"]}
    assert _allows(lease, "fs.read", "/ws/a") is True
    assert _allows(lease, "fs.read", "/ws/a/b/c") is True


def test_net_fetch_single_star_does_not_cross_path_segment() -> None:
    lease = {"net.fetch": ["https://h/*"]}
    assert _allows(lease, "net.fetch", "https://h/a") is True
    assert _allows(lease, "net.fetch", "https://h/a/b") is False


def test_canonicalize_resolves_dotdot() -> None:
    assert canonicalize_target("/ws/sub/../a") == "/ws/a"
    assert canonicalize_target("/ws/../etc/passwd") == "/etc/passwd"


def test_traversal_is_denied_after_canonicalization() -> None:
    lease = {"fs.read": ["/ws/*"]}
    # `/ws/sub/../a` canonicalizes to `/ws/a` (allowed)…
    assert _allows(lease, "fs.read", "/ws/sub/../a") is True
    # …but `/ws/../etc/passwd` canonicalizes to `/etc/passwd` (denied).
    assert _allows(lease, "fs.read", "/ws/../etc/passwd") is False


# ---- #85: sound subset containment ---------------------------------------


def test_globstar_child_is_not_subset_of_single_star_parent() -> None:
    assert is_lease_subset({"fs.read": ["/data/**"]}, {"fs.read": ["/data/*"]}) is False


def test_single_star_child_is_subset_of_globstar_parent() -> None:
    assert is_lease_subset({"fs.read": ["/data/*"]}, {"fs.read": ["/data/**"]}) is True


def test_model_use_child_outside_parent_set_rejected() -> None:
    assert (
        is_lease_subset({"model.use": ["tier-fast/*-preview/*"]}, {"model.use": ["tier-fast/*"]})
        is False
    )
    assert is_lease_subset({"model.use": ["anthropic/*"]}, {"model.use": ["tier-fast/*"]}) is False


def test_identical_and_narrower_children_are_subsets() -> None:
    assert is_lease_subset({"fs.read": ["/data/*"]}, {"fs.read": ["/data/*"]}) is True
    assert is_lease_subset({"fs.read": ["/data/x.txt"]}, {"fs.read": ["/data/*"]}) is True
    assert is_lease_subset({"fs.read": ["/data/x.txt"]}, {"fs.read": ["/data/**"]}) is True


def test_wildcard_widening_within_segment_rejected() -> None:
    # parent literal cannot be widened by a child wildcard.
    assert is_lease_subset({"fs.read": ["/data/*"]}, {"fs.read": ["/data/log.txt"]}) is False


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
