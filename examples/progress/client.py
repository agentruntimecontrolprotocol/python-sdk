"""progress client — renders a text progress bar from progress events."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7892"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="progress-client", version="1.0.0"),
        token=TOKEN,
        features=("progress",),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        handle = await client.submit(agent="report", input={"steps": 10})
        last_current = 0
        async for ev in handle.events():
            if ev["kind"] == "progress":
                body = ev["body"]
                cur, tot = body["current"], body.get("total", 0)
                bar = "#" * cur + "-" * (tot - cur) if tot else ""
                sys.stdout.write(f"\r[{bar}] {cur}/{tot}")
                sys.stdout.flush()
                last_current = cur
        sys.stdout.write("\n")
        result = await handle.done
        assert result.final_status == "success"
        assert last_current == 10
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
