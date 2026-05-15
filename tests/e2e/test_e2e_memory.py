"""End-to-end happy path over MemoryTransport — covers session, submit, events, terminal."""

from __future__ import annotations

import asyncio

from arcp import ClientInfo, RuntimeInfo, pair_memory_transports
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier


async def test_submit_and_stream_e2e() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )

    async def echo(input_value, ctx: JobContext):
        await ctx.log("info", "starting")
        await ctx.status("running")
        await ctx.metric({"name": "tokens.in", "value": 10, "unit": "tokens"})
        return {"echoed": input_value}

    rt.register_agent("echo", echo)

    a, b = pair_memory_transports()
    server = asyncio.create_task(rt.accept(a))
    client = ARCPClient(client=ClientInfo(name="c", version="1"), token="tok")
    try:
        welcome = await client.connect(b)
        assert "ack" in welcome.capabilities.features
        handle = await client.submit(agent="echo", input={"k": 1})
        events = []
        async for ev in handle.events():
            events.append(ev["kind"])
        result = await handle.done
        assert result.final_status == "success"
        assert result.result == {"echoed": {"k": 1}}
        assert "log" in events
        assert "status" in events
        assert "metric" in events
    finally:
        await client.close()
        await rt.close()
        server.cancel()


async def test_idempotency_dedupes() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )

    async def echo(input_value, ctx: JobContext):
        return input_value

    rt.register_agent("echo", echo)

    a, b = pair_memory_transports()
    server = asyncio.create_task(rt.accept(a))
    client = ARCPClient(client=ClientInfo(name="c", version="1"), token="tok")
    try:
        await client.connect(b)
        h1 = await client.submit(agent="echo", input={"x": 1}, idempotency_key="k1")
        h2 = await client.submit(agent="echo", input={"x": 1}, idempotency_key="k1")
        assert h1.job_id == h2.job_id
    finally:
        await client.close()
        await rt.close()
        server.cancel()
