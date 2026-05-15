"""submit_and_stream client — observes events and asserts terminal success."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7879"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="submit-and-stream-client", version="1.0.0"),
        token=TOKEN,
        features=(),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        handle = await client.submit(agent="echo", input={"hello": "world"})
        count = 0
        async for ev in handle.events():
            count += 1
            print(f"[event {count}] kind={ev['kind']} body={ev['body']}")
        result = await handle.done
        print(f"terminal: {result.final_status} (events={count})")
        assert result.final_status == "success", result
        assert count >= 7, f"expected >= 7 events, got {count}"
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
