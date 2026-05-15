"""cost_budget — lease grants `USD:1.00`; agent decrements with `cost.*` metrics (§9.6)."""

from __future__ import annotations

import asyncio
import os

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7891"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def caller(input: dict, ctx: JobContext) -> dict:
    # Each "call" costs $0.30 USD; the lease grants $1.00, so the 4th drives
    # the per-currency counter ≤ 0 and the runtime surfaces BUDGET_EXHAUSTED.
    for i in range(1, 6):
        try:
            ctx.authorize("cost.budget", "USD")
        except Exception as e:  # BudgetExhaustedError
            await ctx.tool_result(
                {
                    "tool_call_id": f"tc{i}",
                    "error": {"code": e.code, "message": str(e), "retryable": False},  # type: ignore[attr-defined]
                }
            )
            return {"completed": i - 1, "exhausted": True}
        await ctx.metric({"name": "cost.openai", "value": 0.30, "unit": "USD"})
        await ctx.tool_result({"tool_call_id": f"tc{i}", "output": f"call-{i}"})
    return {"completed": 5, "exhausted": False}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="cost-budget-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("caller", caller)
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
