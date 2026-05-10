"""Bearer-token authentication (RFC §8.2 ``bearer``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, override

from arcp.errors import ARCPError, ErrorCode


class TokenValidator(Protocol):
    """Validates an opaque bearer token; returns the principal on success."""

    def validate(self, token: str) -> str: ...


@dataclass
class StaticTokenValidator(TokenValidator):
    """Maps a static set of tokens → principal.

    Reference implementation; production deployments inject their own
    validator that talks to their identity provider.
    """

    tokens: dict[str, str] = field(default_factory=dict[str, str])

    @override
    def validate(self, token: str) -> str:
        principal = self.tokens.get(token)
        if principal is None:
            raise ARCPError(ErrorCode.UNAUTHENTICATED, "bearer token rejected")
        return principal


__all__ = ["StaticTokenValidator", "TokenValidator"]
