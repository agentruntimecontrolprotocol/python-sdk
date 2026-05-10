"""Signed-JWT authentication (RFC §8.2 ``signed_jwt``)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt

from arcp.errors import ARCPError, ErrorCode


@dataclass
class JWTValidator:
    """Validates a signed JWT.

    The ``aud`` claim must match :attr:`audience`. The token must be signed
    with one of the supported algorithms using either a shared secret or an
    asymmetric public key (PEM string).
    """

    secret: str
    audience: str
    algorithms: tuple[str, ...] = ("HS256",)

    def validate(self, token: str) -> str:
        try:
            decoded: dict[str, Any] = jwt.decode(
                token,
                self.secret,
                algorithms=list(self.algorithms),
                audience=self.audience,
            )
        except jwt.PyJWTError as exc:
            raise ARCPError(ErrorCode.UNAUTHENTICATED, f"jwt rejected: {exc}") from exc
        principal = decoded.get("sub") or decoded.get("principal")
        if not isinstance(principal, str) or not principal:
            raise ARCPError(ErrorCode.UNAUTHENTICATED, "jwt missing 'sub' claim")
        return principal


__all__ = ["JWTValidator"]
