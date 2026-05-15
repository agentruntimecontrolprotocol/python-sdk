"""idempotent_retry client — same key returns same job_id; different agent raises DuplicateKeyError."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, DuplicateKeyError, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7881"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")
KEY = "demo-key-001"


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="idempotent-retry-client", version="1.0.0"),
        token=TOKEN,
        features=(),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)

        h1 = await client.submit(agent="a", input={"x": 1}, idempotency_key=KEY)
        print(f"first submit: job_id={h1.job_id}")
        h2 = await client.submit(agent="a", input={"x": 1}, idempotency_key=KEY)
        print(f"retry submit: job_id={h2.job_id}")
        assert h1.job_id == h2.job_id, "idempotent retry MUST return the same job_id"

        try:
            await client.submit(agent="b", input={"x": 1}, idempotency_key=KEY)
        except DuplicateKeyError as e:
            print(f"DuplicateKeyError raised as expected: {e.message}")
            return 0
        raise AssertionError("expected DuplicateKeyError on mutated submit")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
