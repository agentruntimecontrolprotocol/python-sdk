"""§9.6 — budget amount grammar."""

from __future__ import annotations

from decimal import Decimal

import pytest

from arcp import parse_budget_amount


@pytest.mark.parametrize(
    ("raw", "currency", "value"),
    [
        ("USD:5", "USD", Decimal("5")),
        ("USD:5.25", "USD", Decimal("5.25")),
        ("EUR:0", "EUR", Decimal("0")),
    ],
)
def test_parse_ok(raw: str, currency: str, value: Decimal) -> None:
    c, v = parse_budget_amount(raw)
    assert c == currency
    assert v == value


@pytest.mark.parametrize(
    "bad",
    [
        "USD-5",  # wrong delimiter
        "5:USD",
        "USD:",
        ":5",
        "USD:abc",
        "",
    ],
)
def test_parse_bad(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_budget_amount(bad)


def test_negative_rejected() -> None:
    # The regex doesn't allow leading minus; raises ValueError on parse.
    with pytest.raises(ValueError):
        parse_budget_amount("USD:-1")
