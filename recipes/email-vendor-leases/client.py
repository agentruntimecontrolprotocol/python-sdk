"""email-vendor-leases client — submit triage with a lease that omits send_reply.

Submits the triage task with a lease that allows the read-only tools
but deliberately omits send_reply, so Claude's eventual attempt to
send hits PERMISSION_DENIED and degrades gracefully.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7900"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="triage-client", version="1.0.0"),
        token=TOKEN,
        features=(),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        # the lease grants tool.call only for read-only inbox tools. send_reply
        # is intentionally absent — when Claude proposes that tool the agent's
        # ctx.authorize raises PermissionDenied and a tool_result error is fed
        # back. the model recovers and returns a drafted (not-sent) reply.
        handle = await client.submit(
            agent="triage",
            input={},
            lease_request={"tool.call": ["inbox_list", "inbox_read"]},
        )
        async for ev in handle.events():
            if ev["kind"] == "tool_result" and ev["body"].get("error"):
                print(f"denied: {ev['body']['error']['message']}")
            elif ev["kind"] == "x-vendor.acme.email.parsed":
                print(f"parsed: {ev['body']['subject']} (urgency={ev['body']['urgency']})")
        result = await handle.done
        print(f"terminal: {result.final_status} drafted={result.result}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
