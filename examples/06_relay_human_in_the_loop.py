"""06 — relay scenario.

A tool runs that needs human approval, requests a permission, produces an
artifact, and completes. Demonstrates §10 + §12 + §15 + §16 working together.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
from typing import Any

from _common import runtime_and_client

from arcp.envelope import Envelope
from arcp.runtime.job import JobContext


async def deploy(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
    grant = await ctx.request_permission(
        permission="deploy.execute",
        resource=f"env:{args.get('env', 'staging')}",
        operation="rollout",
        requested_lease_seconds=120,
    )
    expires = (datetime.now(tz=UTC) + timedelta(seconds=10)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    confirm = await ctx.request_human_input(
        prompt=f"Confirm deploy to {args.get('env', 'staging')}?",
        response_schema={"type": "object"},
        expires_at=expires,
    )
    return {
        "lease_id": grant["lease_id"],
        "confirmed_by": confirm.get("by", "unknown"),
        "env": args.get("env"),
    }


async def main() -> None:
    async with runtime_and_client() as (rt, client):
        rt.register_tool("deploy", deploy)
        accepted = await client.open()

        invoke = Envelope(
            id="msg_invoke_deploy",
            type="tool.invoke",
            session_id=accepted.session_id,
            payload={"tool": "deploy", "arguments": {"env": "staging"}},
        )
        await client.send(invoke)

        artifact_id: str | None = None
        async for env in client.events():
            if env.type == "permission.request":
                await client.send(
                    Envelope(
                        id=f"grant_{env.id}",
                        type="permission.grant",
                        session_id=accepted.session_id,
                        correlation_id=env.id,
                        payload={
                            "permission": env.payload["permission"],
                            "lease_seconds": 60,
                        },
                    )
                )
            elif env.type == "human.input.request":
                await client.send(
                    Envelope(
                        id=f"resp_{env.id}",
                        type="human.input.response",
                        session_id=accepted.session_id,
                        correlation_id=env.id,
                        payload={"value": {"by": "alice"}},
                    )
                )
            elif env.type == "job.completed":
                # After completion, upload an artifact summarizing what happened.
                blob = base64.b64encode(b"deploy-log: ok\n").decode("ascii")
                ref = await client.request(
                    Envelope(
                        id="msg_art_put",
                        type="artifact.put",
                        session_id=accepted.session_id,
                        payload={
                            "media_type": "text/plain",
                            "size": len(b"deploy-log: ok\n"),
                            "data": blob,
                        },
                    ),
                    timeout=2.0,
                )
                artifact_id = ref.payload["artifact_id"]
                break

        print(f"deploy completed; artifact uploaded: {artifact_id}")


if __name__ == "__main__":
    asyncio.run(main())
