"""Hypothesis strategies for ARCP property tests."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import strategies as st

from arcp._ulid import new_ulid


def ulid_strategy() -> st.SearchStrategy[str]:
    """A ULID strategy. We mint live ULIDs for variety with deterministic shape."""
    return st.builds(lambda _i: new_ulid(), st.integers(0, 1_000_000))


def trace_id_strategy() -> st.SearchStrategy[str]:
    """W3C trace_id: 32 lowercase hex chars, non-zero."""
    return st.from_regex(r"^[0-9a-f]{32}$", fullmatch=True).filter(lambda v: v != "0" * 32)


def session_id_strategy() -> st.SearchStrategy[str]:
    return st.builds(lambda u: f"sess_{u}", ulid_strategy())


def job_id_strategy() -> st.SearchStrategy[str]:
    return st.builds(lambda u: f"job_{u}", ulid_strategy())


def envelope_payloads() -> st.SearchStrategy[dict[str, object]]:
    """Generic dict payload — for envelope round-trip testing."""
    return st.dictionaries(
        keys=st.text(min_size=1, max_size=16),
        values=st.one_of(
            st.text(max_size=32),
            st.integers(),
            st.booleans(),
            st.none(),
            st.lists(st.integers(), max_size=4),
        ),
        max_size=8,
    )


def currency_strategy() -> st.SearchStrategy[str]:
    return st.sampled_from(["USD", "EUR", "GBP", "JPY", "CAD"])


def positive_decimals() -> st.SearchStrategy[Decimal]:
    return st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("10000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    )


def budget_amount_strings() -> st.SearchStrategy[str]:
    return st.builds(lambda c, v: f"{c}:{v}", currency_strategy(), positive_decimals())
