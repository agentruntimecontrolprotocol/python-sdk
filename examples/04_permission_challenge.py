"""04 — permission challenge / lease grant.

Demonstrates RFC sections 15.4 and 15.5: a tool requests a scoped permission,
the client grants it, the runtime materializes a lease.
"""

from __future__ import annotations

import asyncio
from typing import Any

from _common import runtime_and_client

from arcp.envelope import Envelope
from arcp.runtime.job import JobContext


async def writer(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
    grant = await ctx.request_permission(
        permission="filesystem.write",
        resource="/tmp/example",
        operation="write",
        requested_lease_seconds=120,
    )
    return {"lease_id": grant["lease_id"]}


async def main() -> None:
    async with runtime_and_client() as (rt, client):
        rt.register_tool("writer", writer)
        accepted = await client.open()

        invoke = Envelope(
            id="msg_invoke_writer",
            type="tool.invoke",
            session_id=accepted.session_id,
            payload={"tool": "writer", "arguments": {}},
        )
        await client.send(invoke)

        async for env in client.events():
            print(f"<< {env.type}: {env.payload}")
            if env.type == "permission.request":
                grant = Envelope(
                    id=f"grant_{env.id}",
                    type="permission.grant",
                    session_id=accepted.session_id,
                    correlation_id=env.id,
                    payload={
                        "permission": env.payload["permission"],
                        "resource": env.payload.get("resource"),
                        "operation": env.payload.get("operation"),
                        "lease_seconds": 60,
                    },
                )
                await client.send(grant)
            if env.type == "job.completed":
                break


if __name__ == "__main__":
    asyncio.run(main())
