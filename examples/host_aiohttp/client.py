"""host_aiohttp client — hits GET /health then submits a job via WS at /arcp."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

import aiohttp

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7897"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    async with aiohttp.ClientSession() as http:
        async with http.get(f"http://127.0.0.1:{PORT}/health") as r:
            r.raise_for_status()
            body = await r.json()
            print(f"/health -> {body}")
            assert body.get("ok") is True

    client = ARCPClient(
        client=ClientInfo(name="host-aiohttp-client", version="1.0.0"), token=TOKEN, features=()
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        handle = await client.submit(agent="echo", input={"k": 1})
        result = await handle.done
        print(f"job -> {result.final_status}, {result.result}")
        assert result.final_status == "success"
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
