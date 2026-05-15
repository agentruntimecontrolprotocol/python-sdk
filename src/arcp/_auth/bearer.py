"""Bearer-token verifier interface and a static-map implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from .._errors import UnauthenticatedError


class Identity(BaseModel):
    """Resolved identity for an authenticated session principal."""

    principal: str
    scopes: tuple[str, ...] = ()


@runtime_checkable
class BearerVerifier(Protocol):
    """Verify a bearer token and return an `Identity`. Raise `UnauthenticatedError` on failure."""

    async def verify(self, token: str) -> Identity: ...


class StaticBearerVerifier:
    """Map of `token -> principal` for tests, fixtures, and demo runs."""

    def __init__(self, tokens: dict[str, str]) -> None:
        self._tokens = dict(tokens)

    async def verify(self, token: str) -> Identity:
        principal = self._tokens.get(token)
        if principal is None:
            raise UnauthenticatedError("invalid bearer token")
        return Identity(principal=principal)


__all__ = ("BearerVerifier", "Identity", "StaticBearerVerifier")
