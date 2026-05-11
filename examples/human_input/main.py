"""Fan `human.input.request` across channels; resolve on first."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from arcp import ARCPClient, Envelope

from .channels import REGISTRY  # ntfy / email / slack adapters

DESTINATIONS = ("ntfy:phone", "email:oncall", "slack:ops")


def _parse(v: str) -> datetime:
    return datetime.fromisoformat(v.replace("Z", "+00:00"))


async def fan_out(client: ARCPClient, request: Envelope) -> None:
    payload = request.payload
    schema = payload.get("response_schema") or {}
    prompt = str(payload.get("prompt", ""))
    expires_at = _parse(str(payload["expires_at"]))
    timeout = max(
        0.0, expires_at.timestamp() - datetime.now(tz=UTC).timestamp()
    )

    async def ask(dest: str) -> tuple[str, dict[str, object]]:
        return dest, await REGISTRY[dest](prompt, schema)

    tasks = {asyncio.create_task(ask(d)): d for d in DESTINATIONS}
    try:
        done, _ = await asyncio.wait(
            tasks, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()

    if not done:
        # Deadline elapsed; translate timeout into the cancelled-input
        # shape (RFC §12.4).
        await client.send(
            client.envelope(
                "human.input.cancelled",
                correlation_id=request.id,
                payload={
                    "code": "DEADLINE_EXCEEDED",
                    "message": "no channel responded before expires_at",
                },
            )
        )
        return

    winner = next(iter(done))
    responded_by, value = winner.result()
    await client.send(
        client.envelope(
            "human.input.response",
            correlation_id=request.id,
            payload={
                "value": value,
                "responded_by": responded_by,
                "responded_at": datetime.now(tz=UTC).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            },
        )
    )
    # Tell the losing destinations the question is settled. Each
    # channel adapter would translate this to "delete the push" /
    # "edit the slack message to '(answered)'".
    losers = tuple(d for t, d in tasks.items() if t is not winner)
    if losers:
        await client.send(
            client.envelope(
                "human.input.cancelled",
                correlation_id=request.id,
                payload={
                    "code": "OK",
                    "message": "answered elsewhere",
                    "channels": list(losers),
                },
            )
        )


async def main() -> None:
    client = ARCPClient(...)  # transport, identity, auth elided
    await client.open()
    runners: set[asyncio.Task[None]] = set()
    try:
        async for env in client.events():
            if env.type == "human.input.request":
                t = asyncio.create_task(fan_out(client, env))
                runners.add(t)
                t.add_done_callback(runners.discard)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
