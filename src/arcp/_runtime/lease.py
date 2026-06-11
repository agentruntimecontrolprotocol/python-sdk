"""Lease helpers: shape validation, op authorization, subset checks, budget arithmetic."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
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
    constraints: LeaseConstraints | None, *, now: dt.datetime | None = None
) -> None:
    """Reject `expires_at` in the past."""
    if constraints is None or constraints.expires_at is None:
        return
    expiry = _parse_iso_utc(constraints.expires_at)
    n = now or dt.datetime.now(dt.UTC)
    if expiry <= n:
        raise InvalidRequestError(
            f"lease_constraints.expires_at must be in the future: {constraints.expires_at!r}"
        )


def _parse_iso_utc(value: str) -> dt.datetime:
    # Python 3.11+ `fromisoformat` accepts `Z` natively; no rewrite needed.
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed


@dataclass(frozen=True)
class LeaseOpContext:
    """Minimal context for a lease-authorized op."""

    capability: str
    target: str
    cost: dict[str, Decimal] | None = None
    now: dt.datetime | None = None


_GlobToken = tuple[str, str]  # ("lit", ch) | ("star", "") | ("globstar", "")

# Capabilities whose targets are filesystem paths; canonicalized (incl. `..`
# resolution) before matching so traversal cannot escape a segment-anchored
# grant. URL/name capabilities (net.fetch, tool.call, model.use, ...) are
# matched verbatim so their `//` and structure survive.
_PATH_CAPABILITIES: frozenset[str] = frozenset({"fs.read", "fs.write"})


def _tokenize_glob(pattern: str) -> tuple[_GlobToken, ...]:
    """Split a lease glob into literal / `*` (single-segment) / `**` tokens."""
    tokens: list[_GlobToken] = []
    i = 0
    n = len(pattern)
    while i < n:
        if pattern[i] == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                tokens.append(("globstar", ""))
                i += 2
            else:
                tokens.append(("star", ""))
                i += 1
        else:
            tokens.append(("lit", pattern[i]))
            i += 1
    return tuple(tokens)


@lru_cache(maxsize=4096)
def _compile_glob(pattern: str) -> re.Pattern[str]:
    """Compile a lease glob to an anchored regex.

    `*` matches within a single path segment (`[^/]*`) and `**` matches across
    separators (`.*`), so a single `*` no longer authorizes deeper paths.
    """
    parts: list[str] = []
    for kind, ch in _tokenize_glob(pattern):
        if kind == "lit":
            parts.append(re.escape(ch))
        elif kind == "star":
            parts.append("[^/]*")
        else:
            parts.append(".*")
    return re.compile("".join(parts))


def _glob_match(patterns: list[str], target: str) -> bool:
    return any(_compile_glob(p).fullmatch(target) is not None for p in patterns)


def _glob_alphabet(*token_lists: tuple[_GlobToken, ...]) -> tuple[str, ...]:
    lits = {ch for tokens in token_lists for kind, ch in tokens if kind == "lit"}
    syms: set[str] = set(lits)
    syms.add("/")
    # A representative non-slash character that is not used as any literal, so
    # `*`/`**` can be distinguished from a concrete literal in the product.
    other = "\x00"
    while other in lits or other == "/":
        other = chr(ord(other) + 1)
    syms.add(other)
    return tuple(syms)


def _eps_closure(tokens: tuple[_GlobToken, ...], states: frozenset[int]) -> frozenset[int]:
    # `*`/`**` may match the empty string, so they carry an epsilon edge to the
    # next position.
    seen = set(states)
    stack = list(states)
    while stack:
        s = stack.pop()
        if s < len(tokens) and tokens[s][0] in ("star", "globstar") and s + 1 not in seen:
            seen.add(s + 1)
            stack.append(s + 1)
    return frozenset(seen)


def _glob_step(
    tokens: tuple[_GlobToken, ...], states: frozenset[int], symbol: str
) -> frozenset[int]:
    out: set[int] = set()
    for s in states:
        if s >= len(tokens):
            continue
        kind, ch = tokens[s]
        if kind == "lit":
            if symbol == ch:
                out.add(s + 1)
        elif kind == "star":
            if symbol != "/":  # single segment: never crosses a separator
                out.add(s)
        else:  # globstar consumes any character, including '/'
            out.add(s)
    return _eps_closure(tokens, frozenset(out))


@lru_cache(maxsize=4096)
def _glob_lang_subset(child: str, parent: str) -> bool:
    """True iff every concrete target matched by `child` is matched by `parent`.

    Decided exactly via a product walk over the two glob automata on a finite
    symbolic alphabet (each literal char, `/`, and one representative other
    non-slash char). If a reachable product state accepts in the child but not
    the parent, the child can name a resource the parent cannot — not a subset.
    """
    ct = _tokenize_glob(child)
    pt = _tokenize_glob(parent)
    alphabet = _glob_alphabet(ct, pt)
    start = (_eps_closure(ct, frozenset({0})), _eps_closure(pt, frozenset({0})))
    seen = {start}
    stack = [start]
    while stack:
        cs, ps = stack.pop()
        if len(ct) in cs and len(pt) not in ps:
            return False
        for sym in alphabet:
            ncs = _glob_step(ct, cs, sym)
            if not ncs:
                continue  # child can match nothing further on this path
            nxt = (ncs, _glob_step(pt, ps, sym))
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return True


DEFAULT_EXPIRY_GRACE_SEC: float = 1.0
"""Bounded grace window applied to `expires_at` enforcement (§14).

`expires_at` is an absolute ISO timestamp, so its comparison is inherently
wall-clock; deployments rely on NTP discipline. The grace absorbs small clock
skew (e.g. an NTP step) so a barely-unexpired lease is not spuriously rejected.
"""


def validate_lease_op(
    lease: Lease,
    ctx: LeaseOpContext,
    *,
    constraints: LeaseConstraints | None = None,
    budget: dict[str, Decimal] | None = None,
    grace_sec: float = DEFAULT_EXPIRY_GRACE_SEC,
) -> None:
    """Authorize an op against the lease: pattern match, expiry, budget. Raise on violation."""
    if constraints is not None and constraints.expires_at is not None:
        n = ctx.now or dt.datetime.now(dt.UTC)
        expiry = _parse_iso_utc(constraints.expires_at) + dt.timedelta(seconds=grace_sec)
        if n >= expiry:
            raise LeaseExpiredError("lease has expired")

    patterns = lease.get(ctx.capability)
    # Filesystem targets are canonicalized (resolving `..`) so traversal cannot
    # escape a segment-anchored grant before matching.
    target = (
        canonicalize_target(ctx.target)
        if ctx.capability in _PATH_CAPABILITIES
        else ctx.target
    )
    if not patterns or not _glob_match(patterns, target):
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
    """Each child pattern's language must be contained in some parent pattern.

    Subset means "every concrete resource the child pattern can match is also
    matched by a parent pattern" (§9.4) — decided structurally via glob-language
    containment, not by matching the child *pattern string* against the parent
    glob (which let a wider child like `/data/**` pass under `/data/*`).
    """
    for cp in child_patterns:
        if not any(_glob_lang_subset(cp, pp) for pp in parent_patterns):
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
    """Normalize a path target before matching.

    Collapses repeated slashes, resolves `.`/`..` segments (so traversal
    cannot escape a grant), and strips a trailing slash.
    """
    collapsed = re.sub(r"/+", "/", target)
    leading = collapsed.startswith("/")
    resolved: list[str] = []
    for seg in collapsed.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if resolved and resolved[-1] != "..":
                resolved.pop()
            elif not leading:
                resolved.append("..")
            # leading-slash with nothing to pop clamps at root.
            continue
        resolved.append(seg)
    out = "/".join(resolved)
    if leading:
        out = "/" + out
    if len(out) > 1 and out.endswith("/"):
        out = out[:-1]
    return out if out else ("/" if leading else "")


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
