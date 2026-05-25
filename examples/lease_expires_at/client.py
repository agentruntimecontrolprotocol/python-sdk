"""lease_expires_at client — submits with `expires_at = now + 2s` and expects LEASE_EXPIRED."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import os
import sys

from arcp import ClientInfo, LeaseConstraints, LeaseExpiredError, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7890"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="lease-expires-at-client", version="1.0.0"),
        token=TOKEN,
        features=("lease_expires_at",),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        expires_at = (
            (dt.datetime.now(dt.UTC) + dt.timedelta(seconds=2)).isoformat().replace("+00:00", "Z")
        )
        handle = await client.submit(
            agent="slow",
            lease_constraints=LeaseConstraints(expires_at=expires_at),
        )
        try:
            await handle.done
            print("UNEXPECTED success")
            return 1
        except LeaseExpiredError as e:
            print(f"terminal: LEASE_EXPIRED ({e.message})")
            return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
