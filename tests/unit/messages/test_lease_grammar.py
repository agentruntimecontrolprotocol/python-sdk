"""§9.2 — lease capability grammar."""

from __future__ import annotations

import pytest

from arcp import InvalidRequestError, LeaseSubsetViolationError
from arcp.runtime import assert_lease_subset, validate_lease_shape


@pytest.mark.parametrize(
    "ns",
    [
        "fs.read",
        "fs.write",
        "net.fetch",
        "tool.call",
        "agent.delegate",
        "cost.budget",
        "model.use",
    ],
)
def test_reserved_namespaces_accepted(ns: str) -> None:
    if ns == "cost.budget":
        validate_lease_shape({ns: ["USD:1.00"]})
    else:
        validate_lease_shape({ns: ["*"]})


def test_child_model_use_strict_subset_ok() -> None:
    assert_lease_subset(
        {"model.use": ["tier-fast/cheap"]},
        {"model.use": ["tier-fast/*"]},
    )


def test_child_model_use_expanded_set_rejected() -> None:
    with pytest.raises(LeaseSubsetViolationError):
        assert_lease_subset(
            {"model.use": ["anthropic/*"]},
            {"model.use": ["tier-fast/*"]},
        )


def test_vendor_namespace_accepted() -> None:
    validate_lease_shape({"x-vendor.foo": ["*"]})


def test_unknown_namespace_rejected() -> None:
    with pytest.raises(InvalidRequestError):
        validate_lease_shape({"unknown.thing": ["*"]})
