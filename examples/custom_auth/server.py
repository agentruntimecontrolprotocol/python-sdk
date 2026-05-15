"""custom_auth — BearerVerifier verifies stateless HMAC-signed principal.exp.hmac tokens."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import time

from arcp import RuntimeInfo, UnauthenticatedError, serve_websocket
from arcp.runtime import ARCPRuntime, Identity, JobContext

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7894"))
SECRET = b"demo-shared-secret"


def make_token(principal: str, lifetime_sec: int = 60) -> str:
    """Build a `principal.exp.hmac` token. Shared by server and client."""
    exp = str(int(time.time()) + lifetime_sec)
    sig = hmac.new(SECRET, f"{principal}.{exp}".encode(), hashlib.sha256).hexdigest()
    return f"{principal}.{exp}.{sig}"


class SignedTokenVerifier:
    """Validate `principal.exp.hmac`; raise UnauthenticatedError on any mismatch."""

    async def verify(self, token: str) -> Identity:
        try:
            principal, exp, sig = token.split(".", 2)
        except ValueError as e:
            raise UnauthenticatedError("malformed token") from e
        if int(exp) < int(time.time()):
            raise UnauthenticatedError("token expired")
        expected = hmac.new(SECRET, f"{principal}.{exp}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise UnauthenticatedError("bad signature")
        return Identity(principal=principal)


async def echo(input: dict, ctx: JobContext) -> dict:
    return {"hello": ctx.job.submitter_principal}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="custom-auth-server", version="1.0.0"),
        bearer=SignedTokenVerifier(),
    )
    runtime.register_agent("echo", echo)
    server = await serve_websocket(runtime.accept, host="127.0.0.1", port=PORT, path="/arcp")
    print(f"listening on ws://127.0.0.1:{PORT}/arcp")
    try:
        await asyncio.Future()
    finally:
        server.close()
        await server.wait_closed()
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
