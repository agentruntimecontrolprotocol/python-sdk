"""#87 — agent-ref grammar matches §7.5."""

from __future__ import annotations

import pytest

from arcp._messages.execution import JobSubmitPayload, parse_agent_ref


def test_version_with_plus_build_metadata_parses() -> None:
    # §7.5 version ::= [a-zA-Z0-9.+_-]+ — `+` is legal SemVer build metadata.
    assert parse_agent_ref("a@1.0.0+linux") == ("a", "1.0.0+linux")
    assert parse_agent_ref("weekly-report@1.0.0+build") == ("weekly-report", "1.0.0+build")
    # Submitting such a ref must not raise.
    assert JobSubmitPayload(agent="weekly-report@1.0.0+build").agent == "weekly-report@1.0.0+build"


def test_leading_digit_name_parses() -> None:
    # §7.5 name ::= [a-z0-9][a-z0-9._-]* — a leading digit is legal.
    assert parse_agent_ref("2fa-agent") == ("2fa-agent", None)
    assert parse_agent_ref("2fa-agent@1.0.0") == ("2fa-agent", "1.0.0")


def test_uppercase_names_rejected_per_spec() -> None:
    # The spec name grammar is lowercase-only; uppercase names are rejected.
    with pytest.raises(ValueError):
        parse_agent_ref("MyAgent")
    with pytest.raises(ValueError):
        parse_agent_ref("MyAgent@1.0.0")


def test_empty_name_still_rejected() -> None:
    with pytest.raises(ValueError):
        parse_agent_ref("@1.0.0")
