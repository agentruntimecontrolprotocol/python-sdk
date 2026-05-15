"""cost_budget client — observes per-currency counter draining to exhausted."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7891"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="cost-budget-client", version="1.0.0"),
        token=TOKEN,
        features=("cost.budget",),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        handle = await client.submit(
            agent="caller",
            lease_request={"cost.budget": ["USD:1.00"]},
        )
        observed_remaining: list[float] = []
        exhausted_in_tool_result = False
        async for ev in handle.events():
            if ev["kind"] == "metric" and ev["body"].get("name") == "cost.budget.remaining":
                observed_remaining.append(float(ev["body"]["value"]))
            elif (
                ev["kind"] == "tool_result"
                and ev["body"].get("error", {}).get("code") == "BUDGET_EXHAUSTED"
            ):
                exhausted_in_tool_result = True
        result = await handle.done
        print(
            f"remaining_snapshots={observed_remaining}, exhausted_in_tool_result={exhausted_in_tool_result}"
        )
        assert result.final_status == "success"
        assert exhausted_in_tool_result
        assert observed_remaining == sorted(observed_remaining, reverse=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
