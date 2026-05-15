"""cancel client — submit, sleep briefly, cancel; expect terminal cancelled."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ARCPError, ClientInfo, WebSocketTransport
from arcp import CancelledError as ARCPCancelled
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7883"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="cancel-client", version="1.0.0"),
        token=TOKEN,
        features=(),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        handle = await client.submit(agent="patient", input={})
        async with asyncio.TaskGroup() as tg:

            async def _consumer() -> None:
                async for ev in handle.events():
                    print(f"[event] kind={ev['kind']}")

            async def _canceller() -> None:
                await asyncio.sleep(1.5)
                print(f"sending job.cancel for {handle.job_id}")
                await client.cancel_job(handle.job_id, reason="demo.cancel")

            tg.create_task(_consumer())
            tg.create_task(_canceller())

        # The job's terminal arrives as a job.error with the cancellation code.
        try:
            async with asyncio.timeout(30):
                await handle.done
        except ARCPCancelled as e:
            print(f"job ended cancelled: code={e.code}")
            return 0
        except ARCPError as e:
            print(f"job ended with ARCPError: code={e.code}")
            assert e.code == "CANCELLED", e
            return 0
    raise AssertionError("expected job.error with CANCELLED")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
