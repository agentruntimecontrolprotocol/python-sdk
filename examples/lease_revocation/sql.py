"""SQL classifier — sqlglot-backed in production."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class StatementClass:
    op: Literal["read", "write", "ddl"]
    tables: frozenset[str]


def classify(sql: str) -> StatementClass:
    # Real version: sqlglot.parse_one(sql, read="postgres") +
    # exp.Table walk for tables, isinstance against Insert / Update /
    # Delete / Merge / Create / Drop / AlterTable for op.
    raise NotImplementedError
