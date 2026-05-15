"""ack_backpressure — server detects ack lag vs. emitted seq and emits status back_pressure."""

from __future__ import annotations

import asyncio
import os

from arcp import Capabilities, RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7886"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def chatty_agent(input: dict, ctx: JobContext) -> dict:
    sess = ctx.job.session
    state = sess.state  # SessionState
    # Emit a steady stream and watch ack progress; if ack lags far behind, emit
    # status { phase: "back_pressure" } (spec §6.5).
    LAG_THRESHOLD = 50
    emitted_warning = False
    for i in range(200):
        await ctx.log("info", f"chatter {i}", attributes={"i": i})
        gap = sess.latest_event_seq - state.last_acked_seq
        if not emitted_warning and gap >= LAG_THRESHOLD:
            await ctx.status("back_pressure", message=f"ack lag = {gap}")
            emitted_warning = True
        await asyncio.sleep(0.005)
    return {"emitted": 200, "lagged": emitted_warning}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="ack-backpressure-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
        capabilities=Capabilities(encodings=("json",), features=("ack",)),
    )
    runtime.register_agent("chatty", chatty_agent)
    server = await serve_websocket(runtime.accept, host="127.0.0.1", port=PORT, path="/arcp")
    print(f"listening on ws://127.0.0.1:{PORT}/arcp")
    try:
        await asyncio.Future()
    finally:
        server.close()
        await server.wait_closed()
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
