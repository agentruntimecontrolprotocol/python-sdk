"""Lease helpers: shape validation, op authorization, subset checks, budget arithmetic."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from .._errors import (
    BudgetExhaustedError,
    InvalidRequestError,
    LeaseExpiredError,
    PermissionDeniedError,
)
from .._messages.execution import (
    Lease,
    LeaseConstraints,
    parse_budget_amount,
)

RESERVED_CAPABILITIES: frozenset[str] = frozenset(
    {
        "fs.read",
        "fs.write",
        "net.fetch",
        "tool.call",
        "agent.delegate",
        "cost.budget",
        "model.use",
    }
)


def _is_valid_capability_namespace(ns: str) -> bool:
    if ns in RESERVED_CAPABILITIES:
        return True
    return ns.startswith("x-vendor.")


def validate_lease_shape(lease: Lease) -> None:
    """Check capability namespaces and pattern shape; raise `InvalidRequestError`."""
    for ns, patterns in lease.items():
        if not _is_valid_capability_namespace(ns):
            raise InvalidRequestError(f"unknown lease capability namespace: {ns!r}")
        if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise InvalidRequestError(f"lease patterns for {ns!r} must be list[str]")
        if ns == "cost.budget":
            for p in patterns:
                parse_budget_amount(p)


def validate_lease_constraints(
    constraints: LeaseConstraints | None, *, now: datetime | None = None
) -> None:
    """Reject `expires_at` in the past."""
    if constraints is None or constraints.expires_at is None:
        return
    expiry = _parse_iso_utc(constraints.expires_at)
    n = now or datetime.now(UTC)
    if expiry <= n:
        raise InvalidRequestError(
            f"lease_constraints.expires_at must be in the future: {constraints.expires_at!r}"
        )


def _parse_iso_utc(value: str) -> datetime:
    s = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


@dataclass(frozen=True)
class LeaseOpContext:
    """Minimal context for a lease-authorized op."""

    capability: str
    target: str
    cost: dict[str, Decimal] | None = None
    now: datetime | None = None


def _glob_match(patterns: list[str], target: str) -> bool:
    return any(fnmatch.fnmatchcase(target, p) for p in patterns)


def validate_lease_op(
    lease: Lease,
    ctx: LeaseOpContext,
    *,
    constraints: LeaseConstraints | None = None,
    budget: dict[str, Decimal] | None = None,
) -> None:
    """Authorize an op against the lease: pattern match, expiry, budget. Raise on violation."""
    if constraints is not None and constraints.expires_at is not None:
        n = ctx.now or datetime.now(UTC)
        expiry = _parse_iso_utc(constraints.expires_at)
        if n >= expiry:
            raise LeaseExpiredError("lease has expired")

    patterns = lease.get(ctx.capability)
    if not patterns or not _glob_match(patterns, ctx.target):
        raise PermissionDeniedError(
            f"operation {ctx.capability}:{ctx.target} not permitted by lease"
        )

    if budget is not None:
        for currency, remaining in budget.items():
            if remaining <= 0:
                raise BudgetExhaustedError(
                    f"budget for {currency} exhausted (remaining={remaining})"
                )


def initial_budget_from_lease(lease: Lease) -> dict[str, Decimal]:
    """Sum `cost.budget: ["USD:5", ...]` patterns into per-currency totals."""
    out: dict[str, Decimal] = {}
    for raw in lease.get("cost.budget", []):
        currency, value = parse_budget_amount(raw)
        out[currency] = out.get(currency, Decimal("0")) + value
    return out


def _is_subset_pattern(child_patterns: list[str], parent_patterns: list[str]) -> bool:
    """A child's pattern is a subset iff every concrete match is also matched by parent."""
    # Conservative implementation: each child pattern must equal a parent pattern,
    # be a strict literal prefix of one (no wildcards in parent prefix), or be
    # entirely matched by a parent glob containing `*`.
    for cp in child_patterns:
        ok = False
        for pp in parent_patterns:
            if cp == pp:
                ok = True
                break
            if "*" in pp and fnmatch.fnmatchcase(cp, pp):
                ok = True
                break
        if not ok:
            return False
    return True


def _patterns_are_subset(child: Lease, parent: Lease) -> bool:
    for ns, patterns in child.items():
        if ns == "cost.budget":
            continue
        parent_patterns = parent.get(ns)
        if not parent_patterns:
            return False
        if not _is_subset_pattern(patterns, parent_patterns):
            return False
    return True


def _budget_fits(child: Lease, parent_remaining: dict[str, Decimal] | None) -> bool:
    if "cost.budget" not in child or parent_remaining is None:
        return True
    for currency, amount in initial_budget_from_lease(child).items():
        if amount > parent_remaining.get(currency, Decimal("0")):
            return False
    return True


def _expiry_fits(
    child_constraints: LeaseConstraints | None,
    parent_constraints: LeaseConstraints | None,
) -> bool:
    if child_constraints is None or child_constraints.expires_at is None:
        return True
    if parent_constraints is None or parent_constraints.expires_at is None:
        return True
    return _parse_iso_utc(child_constraints.expires_at) <= _parse_iso_utc(
        parent_constraints.expires_at
    )


def is_lease_subset(
    child: Lease,
    parent: Lease,
    *,
    parent_budget_remaining: dict[str, Decimal] | None = None,
    parent_constraints: LeaseConstraints | None = None,
    child_constraints: LeaseConstraints | None = None,
) -> bool:
    """Spec §9.4: child lease must be a strict subset of parent (incl. budget + expiry)."""
    return (
        _patterns_are_subset(child, parent)
        and _budget_fits(child, parent_budget_remaining)
        and _expiry_fits(child_constraints, parent_constraints)
    )


def assert_lease_subset(
    child: Lease,
    parent: Lease,
    *,
    parent_budget_remaining: dict[str, Decimal] | None = None,
    parent_constraints: LeaseConstraints | None = None,
    child_constraints: LeaseConstraints | None = None,
) -> None:
    """Raise `LeaseSubsetViolationError` when child is not a subset of parent."""
    if not is_lease_subset(
        child,
        parent,
        parent_budget_remaining=parent_budget_remaining,
        parent_constraints=parent_constraints,
        child_constraints=child_constraints,
    ):
        from .._errors import LeaseSubsetViolationError

        raise LeaseSubsetViolationError("child lease is not a subset of parent")


def canonicalize_target(target: str) -> str:
    """Normalize a target string (collapse `//`, strip trailing slash). Used for matching."""
    out = re.sub(r"/+", "/", target)
    if len(out) > 1 and out.endswith("/"):
        out = out[:-1]
    return out


def echo_budget_for_accept(
    initial: dict[str, Decimal],
) -> dict[str, str] | None:
    """Format the initial budget per-currency for `job.accepted.payload.budget`."""
    if not initial:
        return None
    return {currency: f"{currency}:{value}" for currency, value in initial.items()}


__all__ = (
    "RESERVED_CAPABILITIES",
    "LeaseOpContext",
    "_parse_iso_utc",
    "assert_lease_subset",
    "canonicalize_target",
    "echo_budget_for_accept",
    "initial_budget_from_lease",
    "is_lease_subset",
    "validate_lease_constraints",
    "validate_lease_op",
    "validate_lease_shape",
)


# Suppress unused-import warning by referencing Any only when type-checking.
_: Any = None
