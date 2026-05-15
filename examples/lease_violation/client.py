"""lease_violation client — submits with fs.read-only lease; expects tool_result.error."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7882"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="lease-violation-client", version="1.0.0"),
        token=TOKEN,
        features=(),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        handle = await client.submit(
            agent="cautious",
            input={},
            lease_request={"fs.read": ["/tmp/*"]},
        )
        denied = False
        async for ev in handle.events():
            if ev["kind"] == "tool_result":
                err = ev["body"].get("error")
                # Pattern-match-style assertion on the typed body.
                match err:
                    case {"code": "PERMISSION_DENIED"}:
                        denied = True
                        print(f"observed PERMISSION_DENIED in tool_result: {err['message']}")
        result = await handle.done
        print(f"terminal: {result.final_status}")
        assert denied, "expected at least one tool_result with PERMISSION_DENIED"
        assert result.final_status == "success", result
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
