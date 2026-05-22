"""JWT bearer-token verifier; supports HS256 (shared secret) and JWKS (RS/ES)."""

from __future__ import annotations

from typing import Any

import jwt

from .._errors import UnauthenticatedError
from .bearer import Identity


class JWTVerifier:
    """Verify JWTs against a static secret/public key or a JWKS document."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        secret: str | None = None,
        algorithms: tuple[str, ...] = ("HS256",),
        audience: str | None = None,
        issuer: str | None = None,
        principal_claim: str = "sub",
        scopes_claim: str = "scope",
        jwks: dict[str, Any] | None = None,
    ) -> None:
        # PLR0913: every parameter is an optional, keyword-only configuration
        # knob (no positional args). Grouping into a config dataclass would
        # force a breaking signature change with no clarity gain. TODO(arcp/v2):
        # revisit if more knobs are added or a major-version bump lands.
        if secret is None and jwks is None:
            raise ValueError("JWTVerifier requires either secret or jwks")
        self._secret = secret
        self._algorithms = list(algorithms)
        self._audience = audience
        self._issuer = issuer
        self._principal_claim = principal_claim
        self._scopes_claim = scopes_claim
        self._jwks = jwks

    def _key_for(self, token: str) -> Any:
        if self._jwks is None:
            return self._secret
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as e:
            raise UnauthenticatedError(f"invalid JWT header: {e}") from e
        kid = header.get("kid")
        for k in self._jwks.get("keys", []):
            if k.get("kid") == kid:
                return jwt.PyJWK(k).key
        raise UnauthenticatedError(f"no matching JWK for kid={kid!r}")

    async def verify(self, token: str) -> Identity:
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                self._key_for(token),
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.PyJWTError as e:
            raise UnauthenticatedError(f"invalid JWT: {e}") from e
        principal = claims.get(self._principal_claim)
        if not isinstance(principal, str) or not principal:
            raise UnauthenticatedError(f"missing principal claim {self._principal_claim!r}")
        scopes_raw = claims.get(self._scopes_claim, "")
        if isinstance(scopes_raw, str):
            scopes = tuple(s for s in scopes_raw.split() if s)
        elif isinstance(scopes_raw, list):
            scopes = tuple(str(s) for s in scopes_raw)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
        else:
            scopes = ()
        return Identity(principal=principal, scopes=scopes)


__all__ = ("JWTVerifier",)
