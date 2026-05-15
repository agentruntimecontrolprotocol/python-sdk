"""ack_backpressure client — opts into auto-ack but starves it so the server warns."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient, AutoAckOptions

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7886"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    # Starved-ack policy: only ack every 10000 events => never within the demo run.
    client = ARCPClient(
        client=ClientInfo(name="ack-backpressure-client", version="1.0.0"),
        token=TOKEN,
        features=("ack",),
        auto_ack=AutoAckOptions(every_n=10_000, interval_sec=60.0),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        assert "ack" in client.negotiated_features

        handle = await client.submit(agent="chatty", input={})
        backpressure_seen = 0
        async for ev in handle.events():
            if ev["kind"] == "status" and ev["body"].get("phase") == "back_pressure":
                backpressure_seen += 1
                print(f"[back_pressure] {ev['body'].get('message')}")
        result = await handle.done
        print(f"terminal: {result.final_status}; backpressure_seen={backpressure_seen}")
        assert backpressure_seen >= 1, "expected at least one back_pressure status"
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
