"""§5.1 — `arcp` field MUST equal `"1.1"`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp import PROTOCOL_VERSION, Envelope
from arcp._ulid import new_ulid


def test_arcp_constant_is_one_one() -> None:
    assert PROTOCOL_VERSION == "1.1"


def test_envelope_default_arcp_is_one_one() -> None:
    env = Envelope(id=new_ulid(), type="session.ping", payload={})
    assert env.arcp == "1.1"


@pytest.mark.parametrize("bad", ["1", "1.0", "2", "", "01"])
def test_envelope_rejects_wrong_arcp(bad: str) -> None:
    with pytest.raises(ValidationError):
        Envelope(arcp=bad, id=new_ulid(), type="session.ping", payload={})
