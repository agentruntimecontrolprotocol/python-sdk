"""Unit tests for arcp._runtime.lease — shape validation, op authorization, subset checks."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from arcp._errors import (
    BudgetExhaustedError,
    InvalidRequestError,
    LeaseExpiredError,
    LeaseSubsetViolationError,
    PermissionDeniedError,
)
from arcp._runtime.lease import (
    LeaseOpContext,
    assert_lease_subset,
    canonicalize_target,
    initial_budget_from_lease,
    is_lease_subset,
    validate_lease_constraints,
    validate_lease_op,
    validate_lease_shape,
)


def _future_iso(hours: int = 1) -> str:
    return (
        (dt.datetime.now(dt.UTC) + dt.timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
    )


def _past_iso(hours: int = 1) -> str:
    return (
        (dt.datetime.now(dt.UTC) - dt.timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
    )


# ---------------------------------------------------------------------------
# validate_lease_shape
# ---------------------------------------------------------------------------


def test_validate_lease_shape_valid_reserved_namespace() -> None:
    validate_lease_shape({"fs.read": ["*"]})  # must not raise


def test_validate_lease_shape_valid_vendor_namespace() -> None:
    validate_lease_shape({"x-vendor.my-cap": ["*"]})  # must not raise


def test_validate_lease_shape_unknown_namespace_raises() -> None:
    with pytest.raises(InvalidRequestError, match="unknown lease capability namespace"):
        validate_lease_shape({"totally.unknown": ["*"]})


def test_validate_lease_shape_patterns_not_list_raises() -> None:
    with pytest.raises(InvalidRequestError, match="must be list"):
        validate_lease_shape({"fs.read": "not-a-list"})  # type: ignore[dict-item]


# ---------------------------------------------------------------------------
# validate_lease_constraints
# ---------------------------------------------------------------------------


def test_validate_lease_constraints_none_is_ok() -> None:
    validate_lease_constraints(None)  # must not raise


def test_validate_lease_constraints_no_expiry_is_ok() -> None:
    from arcp._messages.execution import LeaseConstraints

    validate_lease_constraints(LeaseConstraints(expires_at=None))  # must not raise


def test_validate_lease_constraints_future_expiry_ok() -> None:
    from arcp._messages.execution import LeaseConstraints

    validate_lease_constraints(LeaseConstraints(expires_at=_future_iso()))  # must not raise


def test_validate_lease_constraints_past_expiry_raises() -> None:
    from arcp._messages.execution import LeaseConstraints

    with pytest.raises(InvalidRequestError, match="must be in the future"):
        validate_lease_constraints(LeaseConstraints(expires_at=_past_iso()))


def test_parse_iso_utc_no_timezone_returns_utc() -> None:
    """_parse_iso_utc adds UTC when tzinfo is absent."""
    from arcp._runtime.lease import _parse_iso_utc

    parsed = _parse_iso_utc("2024-01-01T00:00:00")
    assert parsed.tzinfo is dt.UTC


# ---------------------------------------------------------------------------
# validate_lease_op — expiry, pattern, budget
# ---------------------------------------------------------------------------


def test_validate_lease_op_expired_constraints_raises() -> None:
    from arcp._messages.execution import LeaseConstraints

    lease = {"fs.read": ["*"]}
    ctx = LeaseOpContext(capability="fs.read", target="file.txt")
    constraints = LeaseConstraints(expires_at=_past_iso())

    # We override the expiry check by passing a future `now` — but here we want expiry to fire
    with pytest.raises(LeaseExpiredError, match="expired"):
        validate_lease_op(lease, ctx, constraints=constraints)


def test_validate_lease_op_no_patterns_raises_permission_denied() -> None:
    lease: dict = {}  # no capability granted
    ctx = LeaseOpContext(capability="fs.read", target="file.txt")
    with pytest.raises(PermissionDeniedError, match="not permitted"):
        validate_lease_op(lease, ctx)


def test_validate_lease_op_glob_mismatch_raises_permission_denied() -> None:
    lease = {"fs.read": ["data/*"]}
    ctx = LeaseOpContext(capability="fs.read", target="secret/password.txt")
    with pytest.raises(PermissionDeniedError, match="not permitted"):
        validate_lease_op(lease, ctx)


def test_validate_lease_op_exhausted_budget_raises() -> None:
    lease = {"fs.read": ["*"], "cost.budget": ["USD:5"]}
    ctx = LeaseOpContext(capability="fs.read", target="file.txt")
    with pytest.raises(BudgetExhaustedError, match="exhausted"):
        validate_lease_op(lease, ctx, budget={"USD": Decimal("0")})


def test_validate_lease_op_valid_passes() -> None:
    lease = {"fs.read": ["*.txt"]}
    ctx = LeaseOpContext(capability="fs.read", target="notes.txt")
    validate_lease_op(lease, ctx)  # must not raise


# ---------------------------------------------------------------------------
# is_lease_subset / assert_lease_subset
# ---------------------------------------------------------------------------


def test_is_lease_subset_identical_leases() -> None:
    lease = {"fs.read": ["*"]}
    assert is_lease_subset(lease, lease) is True


def test_is_lease_subset_parent_wildcard_covers_child_literal() -> None:
    child = {"fs.read": ["file.txt"]}
    parent = {"fs.read": ["*"]}
    assert is_lease_subset(child, parent) is True


def test_is_lease_subset_child_not_covered_by_parent() -> None:
    child = {"fs.read": ["secret/*"]}
    parent = {"fs.read": ["public/*"]}
    assert is_lease_subset(child, parent) is False


def test_is_lease_subset_child_has_cap_not_in_parent() -> None:
    child = {"fs.write": ["*"]}
    parent = {"fs.read": ["*"]}
    assert is_lease_subset(child, parent) is False


def test_is_lease_subset_child_pattern_not_subset() -> None:
    child = {"net.fetch": ["https://evil.com"]}
    parent = {"net.fetch": ["https://safe.com"]}
    assert is_lease_subset(child, parent) is False


def test_is_lease_subset_budget_child_exceeds_parent_remaining() -> None:
    child = {"cost.budget": ["USD:10"]}
    parent: dict = {}
    assert (
        is_lease_subset(
            child,
            parent,
            parent_budget_remaining={"USD": Decimal("5")},
        )
        is False
    )


def test_is_lease_subset_budget_child_fits_parent_remaining() -> None:
    child = {"cost.budget": ["USD:3"]}
    parent: dict = {}
    assert (
        is_lease_subset(
            child,
            parent,
            parent_budget_remaining={"USD": Decimal("5")},
        )
        is True
    )


def test_is_lease_subset_child_expires_after_parent() -> None:
    from arcp._messages.execution import LeaseConstraints

    child_c = LeaseConstraints(expires_at=_future_iso(hours=10))
    parent_c = LeaseConstraints(expires_at=_future_iso(hours=1))
    # child expires later than parent → not a subset
    assert is_lease_subset({}, {}, child_constraints=child_c, parent_constraints=parent_c) is False


def test_is_lease_subset_child_expires_before_parent() -> None:
    from arcp._messages.execution import LeaseConstraints

    child_c = LeaseConstraints(expires_at=_future_iso(hours=1))
    parent_c = LeaseConstraints(expires_at=_future_iso(hours=10))
    assert is_lease_subset({}, {}, child_constraints=child_c, parent_constraints=parent_c) is True


def test_assert_lease_subset_raises_on_violation() -> None:
    child = {"fs.write": ["*"]}
    parent = {"fs.read": ["*"]}
    with pytest.raises(LeaseSubsetViolationError):
        assert_lease_subset(child, parent)


def test_assert_lease_subset_passes_on_valid() -> None:
    lease = {"fs.read": ["*"]}
    assert_lease_subset(lease, lease)  # must not raise


# ---------------------------------------------------------------------------
# canonicalize_target
# ---------------------------------------------------------------------------


def test_canonicalize_target_collapses_double_slash() -> None:
    # Uses path-style targets; the regex collapses ALL repeated slashes including ://
    assert canonicalize_target("/data//file.txt") == "/data/file.txt"


def test_canonicalize_target_strips_trailing_slash() -> None:
    assert canonicalize_target("/data/file.txt/") == "/data/file.txt"


def test_canonicalize_target_root_slash_preserved() -> None:
    assert canonicalize_target("/") == "/"


def test_canonicalize_target_no_change_needed() -> None:
    assert canonicalize_target("/data/file.txt") == "/data/file.txt"


# ---------------------------------------------------------------------------
# initial_budget_from_lease
# ---------------------------------------------------------------------------


def test_initial_budget_from_lease_sums_correctly() -> None:
    lease = {"cost.budget": ["USD:5", "USD:3"]}
    result = initial_budget_from_lease(lease)
    assert result["USD"] == Decimal("8")


def test_initial_budget_from_lease_empty_returns_empty() -> None:
    assert initial_budget_from_lease({}) == {}
