"""subscribe client — A submits, B subscribes; B's cancel attempt is denied."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ARCPError, ClientInfo, ListJobsFilter, PermissionDeniedError, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7888"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN_A = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")
TOKEN_B = "demo-token-b"


def _new_client(name: str, token: str) -> ARCPClient:
    return ARCPClient(
        client=ClientInfo(name=name, version="1.0.0"),
        token=token,
        features=("list_jobs", "subscribe"),
    )


async def main() -> int:
    client_a = _new_client("subscribe-client-A", TOKEN_A)
    client_b = _new_client("subscribe-client-B", TOKEN_B)
    async with contextlib.aclosing(client_a), contextlib.aclosing(client_b):
        ta = await WebSocketTransport.connect(URL)
        tb = await WebSocketTransport.connect(URL)
        await client_a.connect(ta)
        await client_b.connect(tb)

        handle = await client_a.submit(agent="slow", input={})
        # Let a few events accrue for B to replay.
        await asyncio.sleep(1.0)

        jobs = await client_b.list_jobs(filter=ListJobsFilter(status=("running",)))
        assert any(j.job_id == handle.job_id for j in jobs.jobs), jobs

        sub = await client_b.subscribe(handle.job_id, history=True)
        print(f"subscribed: replayed={sub.replayed} from={sub.subscribed_from}")
        assert sub.replayed > 0

        # B tails at least one live event.
        tail_count = 0
        async for _ in sub.handle.events():
            tail_count += 1
            if tail_count >= 1:
                break
        print(f"B observed {tail_count} live event(s)")
        assert tail_count >= 1

        # B attempts to cancel A's job; expect PermissionDeniedError surfaced as session.error
        # which fails outstanding handles on client B.
        await client_b.cancel_job(handle.job_id, reason="subscriber.cancel")
        denied = False
        try:
            async with asyncio.timeout(5):
                await sub.handle.done
        except PermissionDeniedError as e:
            denied = True
            print(f"B's cancel was denied: {e.message}")
        except ARCPError as e:
            denied = e.code == "PERMISSION_DENIED"
            print(f"B saw ARCPError code={e.code}")
        assert denied, "expected B's cancel to be denied"

        # A's job should still be running (or about to finish on its own).
        await handle.done  # A still owns the handle.
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
