"""agent_versions client — bare resolves, pinned works, missing version raises."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import (
    AgentVersionNotAvailableError,
    ClientInfo,
    WebSocketTransport,
)
from arcp._messages.session import AgentInventoryEntry
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7889"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="agent-versions-client", version="1.0.0"),
        token=TOKEN,
        features=("agent_versions",),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        welcome = await client.connect(transport)
        # Pretty-print the rich agent inventory.
        for entry in welcome.capabilities.agents:
            assert isinstance(entry, AgentInventoryEntry)
            print(f"agent: {entry.name} versions={list(entry.versions)} default={entry.default}")

        # Bare-name (resolves to default).
        h1 = await client.submit(agent="summarize", input={"x": "hello"})
        async for _ in h1.events():
            pass
        r1 = await h1.done
        print(f"bare → {r1.result}")
        assert r1.final_status == "success"

        # Pinned to 1.2.3.
        h2 = await client.submit(agent="summarize@1.2.3", input={"x": "hi"})
        async for _ in h2.events():
            pass
        r2 = await h2.done
        print(f"@1.2.3 → {r2.result}")
        assert r2.final_status == "success"

        # Missing version: expect AgentVersionNotAvailableError on the submit (delivered via session.error).
        try:
            await client.submit(agent="summarize@9.9.9", input={"x": "?"})
        except AgentVersionNotAvailableError as e:
            print(f"@9.9.9 → AgentVersionNotAvailableError: {e.message}")
            return 0
        raise AssertionError("expected AgentVersionNotAvailableError for @9.9.9")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
