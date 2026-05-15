"""§6.2 — `session.hello` payload shape."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp._messages.session import (
    AuthBearer,
    Capabilities,
    ClientInfo,
    SessionHelloPayload,
)


def test_minimal_hello_v10_shape() -> None:
    p = SessionHelloPayload(
        client=ClientInfo(name="c", version="1"),
        auth=AuthBearer(token="t"),
    )
    assert p.capabilities.features == ()


def test_hello_with_features() -> None:
    p = SessionHelloPayload(
        client=ClientInfo(name="c", version="1"),
        auth=AuthBearer(token="t"),
        capabilities=Capabilities(features=("ack", "subscribe")),
    )
    assert p.capabilities.features == ("ack", "subscribe")


def test_auth_scheme_must_be_bearer() -> None:
    with pytest.raises(ValidationError):
        AuthBearer(scheme="basic", token="t")  # type: ignore[arg-type]
