"""Unit tests for arcp.auth.jwt.JWTValidator."""

from __future__ import annotations

import jwt
import pytest

from arcp.auth.jwt import JWTValidator
from arcp.errors import ARCPError, ErrorCode

# PyJWT 2.10+ warns on HS256 secrets shorter than the algorithm's key size; pad to 32 bytes.
_SECRET = "supers3cret-padding-to-32-bytes!"
_AUDIENCE = "arcp-test"


def _token(claims: dict[str, object], *, secret: str = _SECRET, alg: str = "HS256") -> str:
    return jwt.encode(claims, secret, algorithm=alg)


def test_validates_and_returns_sub() -> None:
    v = JWTValidator(secret=_SECRET, audience=_AUDIENCE)
    token = _token({"sub": "alice", "aud": _AUDIENCE})
    assert v.validate(token) == "alice"


def test_falls_back_to_principal_claim() -> None:
    v = JWTValidator(secret=_SECRET, audience=_AUDIENCE)
    token = _token({"principal": "bob", "aud": _AUDIENCE})
    assert v.validate(token) == "bob"


def test_rejects_wrong_audience() -> None:
    v = JWTValidator(secret=_SECRET, audience=_AUDIENCE)
    token = _token({"sub": "alice", "aud": "different"})
    with pytest.raises(ARCPError) as excinfo:
        v.validate(token)
    assert excinfo.value.code == ErrorCode.UNAUTHENTICATED


def test_rejects_bad_signature() -> None:
    v = JWTValidator(secret=_SECRET, audience=_AUDIENCE)
    token = _token(
        {"sub": "alice", "aud": _AUDIENCE},
        secret="wrong-secret-also-32-bytes-pad!!",
    )
    with pytest.raises(ARCPError) as excinfo:
        v.validate(token)
    assert excinfo.value.code == ErrorCode.UNAUTHENTICATED


def test_rejects_missing_sub_and_principal() -> None:
    v = JWTValidator(secret=_SECRET, audience=_AUDIENCE)
    token = _token({"aud": _AUDIENCE})
    with pytest.raises(ARCPError, match="missing 'sub' claim") as excinfo:
        v.validate(token)
    assert excinfo.value.code == ErrorCode.UNAUTHENTICATED


def test_rejects_non_string_sub() -> None:
    v = JWTValidator(secret=_SECRET, audience=_AUDIENCE)
    token = _token({"sub": 12345, "aud": _AUDIENCE})
    with pytest.raises(ARCPError) as excinfo:
        v.validate(token)
    # PyJWT itself rejects non-string sub before our own check runs.
    assert excinfo.value.code == ErrorCode.UNAUTHENTICATED


def test_rejects_empty_string_sub() -> None:
    v = JWTValidator(secret=_SECRET, audience=_AUDIENCE)
    token = _token({"sub": "", "aud": _AUDIENCE})
    with pytest.raises(ARCPError, match="missing 'sub' claim"):
        v.validate(token)
