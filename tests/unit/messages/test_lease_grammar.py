"""§9.2 — lease capability grammar."""

from __future__ import annotations

import pytest

from arcp import InvalidRequestError
from arcp.runtime import validate_lease_shape


@pytest.mark.parametrize(
    "ns",
    ["fs.read", "fs.write", "net.fetch", "tool.call", "agent.delegate", "cost.budget"],
)
def test_reserved_namespaces_accepted(ns: str) -> None:
    if ns == "cost.budget":
        validate_lease_shape({ns: ["USD:1.00"]})
    else:
        validate_lease_shape({ns: ["*"]})


def test_vendor_namespace_accepted() -> None:
    validate_lease_shape({"x-vendor.foo": ["*"]})


def test_unknown_namespace_rejected() -> None:
    with pytest.raises(InvalidRequestError):
        validate_lease_shape({"unknown.thing": ["*"]})
