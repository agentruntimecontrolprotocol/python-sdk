"""§9.8 — provisioned credential payload validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp import CredentialPayload


def test_credential_payload_round_trip() -> None:
    raw = {
        "id": "cred_1",
        "scheme": "bearer",
        "value": "secret",
        "endpoint": "https://gateway.example.test/v1",
        "profile": "openai",
        "constraints": {
            "cost.budget": ["USD:5.00"],
            "model.use": ["tier-fast/*"],
            "expires_at": "2026-05-13T23:42:00Z",
        },
    }

    payload = CredentialPayload.model_validate(raw)

    assert payload.model_dump(by_alias=True, mode="json") == raw


def test_credential_payload_rejects_non_bearer() -> None:
    with pytest.raises(ValidationError):
        CredentialPayload.model_validate(
            {
                "id": "cred_1",
                "scheme": "basic",
                "value": "secret",
                "endpoint": "https://gateway.example.test/v1",
            }
        )


def test_credential_payload_requires_endpoint() -> None:
    with pytest.raises(ValidationError):
        CredentialPayload.model_validate({"id": "cred_1", "scheme": "bearer", "value": "s"})
