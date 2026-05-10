"""03 — human-in-the-loop input request.

Demonstrates RFC §12.1 (human.input.request/response). The example client
auto-responds to make the run scriptable.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from _common import runtime_and_client

from arcp.envelope import Envelope
from arcp.runtime.job import JobContext


async def asker(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
    expires = (datetime.now(tz=UTC) + timedelta(seconds=10)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return await ctx.request_human_input(
        prompt="Which branch should I create?",
        response_schema={"type": "object", "required": ["branch"]},
        expires_at=expires,
    )


async def main() -> None:
    async with runtime_and_client() as (rt, client):
        rt.register_tool("asker", asker)
        accepted = await client.open()

        invoke = Envelope(
            id="msg_invoke_asker",
            type="tool.invoke",
            session_id=accepted.session_id,
            payload={"tool": "asker", "arguments": {}},
        )
        await client.send(invoke)

        async for env in client.events():
            print(f"<< {env.type}: {env.payload}")
            if env.type == "human.input.request":
                print(f"   runtime asks: {env.payload['prompt']}")
                response = Envelope(
                    id=f"resp_{env.id}",
                    type="human.input.response",
                    session_id=accepted.session_id,
                    correlation_id=env.id,
                    payload={"value": {"branch": "fix/example"}},
                )
                await client.send(response)
            if env.type == "job.completed":
                break


if __name__ == "__main__":
    asyncio.run(main())
