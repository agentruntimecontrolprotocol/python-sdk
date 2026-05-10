"""Unit tests for arcp.runtime.session: capability negotiation, handshake driver, refresh."""

from __future__ import annotations

import uuid

from arcp.envelope import Envelope
from arcp.errors import ErrorCode
from arcp.messages.session import (
    AuthBlock,
    Capabilities,
    Identity,
    RuntimeIdentity,
    SessionOpenPayload,
)
from arcp.runtime.session import (
    HandshakeDriver,
    SessionPhase,
    SessionState,
    consume_authenticate,
    negotiate_capabilities,
)


def _runtime_identity() -> RuntimeIdentity:
    return RuntimeIdentity(kind="arcp-py", version="test")


def _client() -> Identity:
    return Identity(kind="agent", version="0.1")


def _open_envelope(scheme: str, *, token: str | None = None, **caps_kw: object) -> Envelope:
    payload = SessionOpenPayload(
        client=_client(),
        capabilities=Capabilities(**caps_kw),  # type: ignore[arg-type]
        auth=AuthBlock(scheme=scheme, token=token),  # type: ignore[arg-type]
    )
    return Envelope(
        id=f"msg_{uuid.uuid4().hex[:12]}",
        type="session.open",
        payload=payload.model_dump(exclude_none=True),
    )


def test_negotiate_rejects_unmet_required_capability() -> None:
    requested = Capabilities(streaming=True)
    advertised = Capabilities(streaming=False)
    result, rejection = negotiate_capabilities(requested, advertised)
    assert rejection is not None
    assert "streaming" in rejection
    # On rejection, function returns the advertised set as-is.
    assert result is advertised


def test_negotiate_intersects_when_both_supplied() -> None:
    requested = Capabilities(streaming=True, artifacts=True)
    advertised = Capabilities(streaming=True, artifacts=True, subscriptions=True)
    result, rejection = negotiate_capabilities(requested, advertised)
    assert rejection is None
    assert result.streaming is True
    assert result.artifacts is True
    # Subscriptions advertised but not requested → off in intersection.
    assert result.subscriptions is False


def test_negotiate_rejects_unknown_extension_namespace() -> None:
    requested = Capabilities(extensions=["bare_name_no_namespace"])
    advertised = Capabilities()
    _, rejection = negotiate_capabilities(requested, advertised)
    assert rejection is not None
    assert "invalid namespace" in rejection


def test_negotiate_rejects_unsupported_extension() -> None:
    requested = Capabilities(extensions=["arcpx.acme.thing.v1"])
    advertised = Capabilities()
    _, rejection = negotiate_capabilities(requested, advertised)
    assert rejection is not None
    assert "not supported" in rejection


def test_handshake_rejects_anonymous_when_capability_off() -> None:
    driver = HandshakeDriver(
        runtime_identity=_runtime_identity(),
        advertised=Capabilities(),
    )
    result = driver.handle_open(_open_envelope("none"))
    assert result.state is None
    assert result.response.type == "session.rejected"
    assert result.response.payload["code"] == str(ErrorCode.UNAUTHENTICATED)


def test_handshake_accepts_anonymous_when_negotiated() -> None:
    driver = HandshakeDriver(
        runtime_identity=_runtime_identity(),
        advertised=Capabilities(anonymous=True),
    )
    result = driver.handle_open(_open_envelope("none", anonymous=True))
    assert result.state is not None
    assert result.state.phase == SessionPhase.ACCEPTED
    assert result.response.type == "session.accepted"


def test_handshake_rejects_unimplemented_scheme() -> None:
    driver = HandshakeDriver(
        runtime_identity=_runtime_identity(),
        advertised=Capabilities(),
    )
    result = driver.handle_open(_open_envelope("mtls"))
    assert result.state is None
    assert result.response.payload["code"] == str(ErrorCode.UNIMPLEMENTED)
    assert "mtls" in result.response.payload["message"]


def test_handshake_rejects_bearer_when_no_validator() -> None:
    driver = HandshakeDriver(
        runtime_identity=_runtime_identity(),
        advertised=Capabilities(),
    )
    result = driver.handle_open(_open_envelope("bearer", token="abc"))
    assert result.state is None
    assert result.response.payload["code"] == str(ErrorCode.UNIMPLEMENTED)


def test_handshake_rejects_bearer_when_token_missing() -> None:
    driver = HandshakeDriver(
        runtime_identity=_runtime_identity(),
        advertised=Capabilities(),
    )
    result = driver.handle_open(_open_envelope("bearer"))
    assert result.state is None
    assert result.response.payload["code"] == str(ErrorCode.UNAUTHENTICATED)


def test_handshake_rejects_signed_jwt_without_validator() -> None:
    driver = HandshakeDriver(
        runtime_identity=_runtime_identity(),
        advertised=Capabilities(),
    )
    result = driver.handle_open(_open_envelope("signed_jwt", token="x.y.z"))
    assert result.response.payload["code"] == str(ErrorCode.UNIMPLEMENTED)


def test_handshake_rejects_malformed_open_payload() -> None:
    driver = HandshakeDriver(
        runtime_identity=_runtime_identity(),
        advertised=Capabilities(),
    )
    bad = Envelope(id="msg_bad", type="session.open", payload={"not": "valid"})
    result = driver.handle_open(bad)
    assert result.state is None
    assert result.response.type == "session.rejected"
    assert result.response.payload["code"] == str(ErrorCode.INVALID_ARGUMENT)


def test_issue_challenge_emits_session_challenge() -> None:
    driver = HandshakeDriver(
        runtime_identity=_runtime_identity(),
        advertised=Capabilities(),
    )
    opening = _open_envelope("bearer", token="t")
    challenge = driver.issue_challenge(opening)
    assert challenge.type == "session.challenge"
    assert challenge.correlation_id == opening.id
    assert "nonce" in challenge.payload
    assert "expires_at" in challenge.payload


def _seed_state(driver: HandshakeDriver) -> SessionState:
    result = driver.handle_open(_open_envelope("none", anonymous=True))
    assert result.state is not None
    return result.state


def test_consume_authenticate_accepts_well_formed() -> None:
    driver = HandshakeDriver(
        runtime_identity=_runtime_identity(),
        advertised=Capabilities(anonymous=True),
    )
    state = _seed_state(driver)
    state.phase = SessionPhase.REFRESHING
    auth_env = Envelope(
        id="msg_auth",
        type="session.authenticate",
        session_id=state.session_id,
        payload={"auth": {"scheme": "none"}},
    )
    response, accepted = consume_authenticate(state, auth_env)
    assert accepted is True
    assert response.type == "session.accepted"
    assert state.phase == SessionPhase.ACCEPTED


def test_consume_authenticate_rejects_malformed() -> None:
    driver = HandshakeDriver(
        runtime_identity=_runtime_identity(),
        advertised=Capabilities(anonymous=True),
    )
    state = _seed_state(driver)
    bad_env = Envelope(
        id="msg_bad",
        type="session.authenticate",
        session_id=state.session_id,
        payload={"not_auth": True},
    )
    response, accepted = consume_authenticate(state, bad_env)
    assert accepted is False
    assert response.type == "session.rejected"
    assert response.payload["code"] == str(ErrorCode.INVALID_ARGUMENT)
