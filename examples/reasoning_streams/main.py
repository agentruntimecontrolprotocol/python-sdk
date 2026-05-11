"""Primary emits reasoning; mirror peer subscribes, critiques back."""

from __future__ import annotations

import asyncio
import uuid

from arcp import ARCPClient, Envelope

from .agents import critique_thought, primary_step  # LLM calls

MAX_DEPTH = 3
TOKEN_BUDGET = 8_000


# Primary side -----------------------------------------------------------


async def run_primary(
    client: ARCPClient,
    *,
    request: str,
    inbound_critiques: asyncio.Queue[dict[str, object]],
) -> str:
    stream_id = f"str_{uuid.uuid4().hex[:10]}"
    await client.send(
        client.envelope(
            "stream.open",
            stream_id=stream_id,
            payload={"kind": "thought"},
        )
    )

    last: dict[str, object] | None = None
    answer = ""
    for step in range(MAX_DEPTH):
        answer = await primary_step(request, last)
        await client.send(
            client.envelope(
                "stream.chunk",
                stream_id=stream_id,
                payload={
                    "sequence": step,
                    "kind": "thought",
                    "role": "assistant_thought",
                    "content": answer,
                },
            )
        )
        try:
            last = await asyncio.wait_for(inbound_critiques.get(), timeout=5.0)
            if last.get("severity") == "halt":
                break
        except TimeoutError:
            last = None
    return answer


# Mirror side (a peer runtime, NOT a pure observer — it both reads
# the thought stream AND delegates critique events back) -----------------


async def subscribe_thoughts(
    mirror: ARCPClient, *, target_session_id: str
) -> str:
    accepted = await mirror.request(
        mirror.envelope(
            "subscribe",
            payload={
                "filter": {
                    "session_id": [target_session_id],
                    "types": ["stream.chunk"],
                }
            },
        ),
        timeout=10.0,
    )
    return str(accepted.payload["subscription_id"])


def is_thought(env: Envelope) -> bool:
    return env.type == "stream.chunk" and (
        env.payload.get("kind") == "thought"
        or env.payload.get("role") == "assistant_thought"
    )


async def run_mirror(
    mirror: ARCPClient,
    *,
    target_session_id: str,
) -> None:
    sub_id = await subscribe_thoughts(
        mirror, target_session_id=target_session_id
    )
    spent = 0
    try:
        async for env in mirror.events():
            if env.type != "subscribe.event":
                continue
            inner = env.payload.get("event")
            if not isinstance(inner, dict):
                continue
            inner_env = Envelope.from_wire(inner)
            if not is_thought(inner_env):
                continue
            if spent >= TOKEN_BUDGET:
                # Tear down cleanly: runtime stops paying for events
                # we'll never act on.
                await mirror.send(
                    mirror.envelope(
                        "unsubscribe",
                        subscription_id=sub_id,
                    )
                )
                return

            severity, summary, suggestion, consumed = await critique_thought(
                str(inner_env.payload.get("content", ""))
            )
            spent += consumed
            await mirror.send(
                mirror.envelope(
                    "agent.delegate",
                    target=target_session_id,
                    payload={
                        "target": "primary",
                        "task": "consume_critique",
                        "context": {
                            "critique": {
                                "target_thought_sequence": int(
                                    inner_env.payload.get("sequence", 0)
                                ),
                                "severity": severity,
                                "summary": summary,
                                "suggestion": suggestion,
                                "consumed_tokens": consumed,
                            }
                        },
                    },
                )
            )
    finally:
        await mirror.send(
            mirror.envelope("unsubscribe", subscription_id=sub_id)
        )


async def main() -> None:
    primary = ARCPClient(...)  # transport, identity, auth elided
    mirror = ARCPClient(...)
    await primary.open()
    await mirror.open()

    inbound: asyncio.Queue[dict[str, object]] = asyncio.Queue()

    async def route() -> None:
        async for env in primary.events():
            if env.type == "agent.delegate":
                critique = env.payload.get("context", {}).get("critique")
                if isinstance(critique, dict):
                    await inbound.put(critique)

    # Both run for main()'s lifetime; we never need to await/cancel.
    asyncio.create_task(route())  # noqa: RUF006
    asyncio.create_task(  # noqa: RUF006
        run_mirror(mirror, target_session_id=primary.session_id or "")
    )

    answer = await run_primary(
        primary,
        request="Argue both sides: serializable vs snapshot iso?",
        inbound_critiques=inbound,
    )
    print(answer)

    await primary.close()
    await mirror.close()


if __name__ == "__main__":
    asyncio.run(main())
