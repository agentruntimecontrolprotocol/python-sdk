"""delegate client — submits parent and asserts trace_id propagated to child."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7878"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="delegate-client", version="1.0.0"),
        token=TOKEN,
        features=(),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        handle = await client.submit(agent="parent", input={"start": True})
        delegate_seen: dict | None = None
        async for ev in handle.events():
            print(f"[event] kind={ev['kind']}")
            if ev["kind"] == "delegate":
                delegate_seen = ev["body"]
        result = await handle.done
        print(f"parent terminal: {result.final_status}; delegate={delegate_seen}")
        assert result.final_status == "success", result
        assert delegate_seen is not None, "delegate event missing"
        body = result.result
        assert body["parent_trace"] == body["child_trace"], (
            f"parent.trace_id != child.trace_id: {body}"
        )
        print(f"trace_id shared across parent/child: {body['parent_trace']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
