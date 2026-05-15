"""custom_auth client — valid token succeeds; invalid token rejected at handshake."""

from __future__ import annotations

import asyncio
import contextlib
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from server import make_token

from arcp import ClientInfo, UnauthenticatedError, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7894"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")


async def _attempt(token: str) -> tuple[bool, str]:
    client = ARCPClient(
        client=ClientInfo(name="custom-auth-client", version="1.0.0"),
        token=token,
        features=(),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        try:
            await client.connect(transport)
        except UnauthenticatedError as e:
            return False, e.message
        handle = await client.submit(agent="echo", input={})
        async for _ in handle.events():
            pass
        result = await handle.done
        return result.final_status == "success", "ok"


async def main() -> int:
    ok, msg = await _attempt(make_token("alice"))
    print(f"valid token: ok={ok} msg={msg}")
    assert ok, msg

    ok2, msg2 = await _attempt("not.a.valid.token")
    print(f"invalid token: ok={ok2} msg={msg2}")
    assert not ok2, "invalid token must be rejected"
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
