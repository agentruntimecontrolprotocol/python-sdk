"""list_jobs client — submit 3 jobs, walk two pages of limit=2 with cursor."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, ListJobsFilter, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7887"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="list-jobs-client", version="1.0.0"),
        token=TOKEN,
        features=("list_jobs",),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        assert "list_jobs" in client.negotiated_features

        for _ in range(3):
            await client.submit(agent="hold", input={})
        # Give the runtime a tick to record the jobs as running.
        await asyncio.sleep(0.1)

        flt = ListJobsFilter(status=("running",))
        page1 = await client.list_jobs(filter=flt, limit=2)
        print(f"page1: count={len(page1.jobs)} next_cursor={page1.next_cursor}")
        assert len(page1.jobs) == 2
        assert page1.next_cursor is not None

        page2 = await client.list_jobs(filter=flt, limit=2, cursor=page1.next_cursor)
        print(f"page2: count={len(page2.jobs)} next_cursor={page2.next_cursor}")
        assert len(page2.jobs) == 1
        assert page2.next_cursor is None

        total = len(page1.jobs) + len(page2.jobs)
        assert total == 3
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
