"""multi-agent-budget client — submit the top-level research question with a USD cap.

Submits the top-level research question with a USD:0.50 cap. The
runtime stamps every event in the delegation tree with a strictly
monotonic event_seq so parent + child streams interleave in one
session; the client doesn't have to demultiplex.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7899"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="research-client", version="1.0.0"),
        token=TOKEN,
        features=("cost.budget",),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        # workers each carve a slice from the planner's remaining budget. when
        # the budget no longer fits a grant the planner drops the sub-question;
        # when a worker overspends inside its own slice that worker job ends
        # with BUDGET_EXHAUSTED while siblings continue.
        handle = await client.submit(
            agent="planner",
            input={"question": "What causes urban heat islands?"},
            lease_request={
                "cost.budget": ["USD:0.50"],
                "tool.call": ["llm.complete"],
                "agent.delegate": ["worker"],
            },
        )
        async for ev in handle.events():
            if ev["kind"] == "delegate":
                print(f"delegated → {ev['body']['child_job_id']}")
        result = await handle.done
        print(f"terminal: {result.final_status}")
        if result.result:
            print(f"dropped {len(result.result.get('dropped', []))} for budget")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
