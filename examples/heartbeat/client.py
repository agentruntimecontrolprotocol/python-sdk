"""heartbeat client — asserts welcome.heartbeat_interval_sec == 5 and feature negotiated."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7885"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    # Advertise ONLY heartbeat so intersection is {"heartbeat"} only.
    client = ARCPClient(
        client=ClientInfo(name="heartbeat-client", version="1.0.0"),
        token=TOKEN,
        features=("heartbeat",),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        welcome = await client.connect(transport)
        print(f"negotiated features: {client.negotiated_features}")
        print(f"welcome.heartbeat_interval_sec: {welcome.heartbeat_interval_sec}")
        assert "heartbeat" in client.negotiated_features
        assert welcome.heartbeat_interval_sec == 5

        handle = await client.submit(agent="long", input={})
        # Wait for the terminal — during this period the client's read pump
        # auto-replies to incoming session.ping with session.pong.
        async with asyncio.timeout(30):
            result = await handle.done
        print(f"terminal: {result.final_status}")
        assert result.final_status == "success"
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
