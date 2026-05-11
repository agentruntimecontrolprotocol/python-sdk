"""Boot three Observer clients on a single producing session."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from arcp import ARCPClient, Envelope

from .sinks.otlp_sink import OTLPSink
from .sinks.sqlite_sink import SQLiteSink
from .sinks.stdout_sink import StdoutSink

STDOUT_TYPES = (
    "log",
    "job.started",
    "job.progress",
    "job.completed",
    "job.failed",
    "tool.error",
)
OTLP_TYPES = ("metric", "trace.span")


async def subscribe(
    client: ARCPClient,
    *,
    session_id: str,
    types: tuple[str, ...] | None = None,
) -> str:
    filter_: dict[str, object] = {"session_id": [session_id]}
    if types is not None:
        filter_["types"] = list(types)
    accepted = await client.request(
        client.envelope("subscribe", payload={"filter": filter_})
    )
    return str(accepted.payload["subscription_id"])


def unwrap_event(envelope: Envelope) -> Envelope | None:
    """Return the inner envelope from a `subscribe.event`, or None to skip."""
    if envelope.type != "subscribe.event":
        return None
    inner = envelope.payload.get("event")
    if not isinstance(inner, dict):
        return None
    return Envelope.from_wire(inner)


async def unsubscribe(client: ARCPClient, subscription_id: str) -> None:
    await client.send(
        client.envelope("unsubscribe", subscription_id=subscription_id)
    )


async def attach(
    types: tuple[str, ...] | None,
    handler: Callable[[Envelope], Awaitable[None]],
) -> None:
    client = ARCPClient(...)  # transport, identity, auth elided
    await client.open()
    sub_id = await subscribe(client, session_id="...", types=types)
    try:
        async for envelope in client.events():
            inner = unwrap_event(envelope)
            if inner is not None:
                await handler(inner)
    finally:
        await unsubscribe(client, sub_id)
        await client.close()


async def main() -> None:
    stdout = StdoutSink()
    otlp = OTLPSink(endpoint="...")
    async with SQLiteSink(path="replay.sqlite") as sqlite:
        await asyncio.gather(
            attach(STDOUT_TYPES, stdout.handle),
            attach(None, sqlite.handle),
            attach(OTLP_TYPES, otlp.handle),
        )


if __name__ == "__main__":
    asyncio.run(main())
