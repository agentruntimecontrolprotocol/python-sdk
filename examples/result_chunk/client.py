"""result_chunk client — reassembles streamed chunks via async iterator."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7893"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="result-chunk-client", version="1.0.0"),
        token=TOKEN,
        features=("result_chunk",),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        handle = await client.submit(agent="report-builder", input={"chunks": 30})
        blob = await handle.collect_chunks()
        result = await handle.done
        print(f"reassembled {len(blob)} bytes; result_size={result.result_size}")
        assert result.final_status == "success"
        assert result.result_size is not None
        assert len(blob) == result.result_size
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
