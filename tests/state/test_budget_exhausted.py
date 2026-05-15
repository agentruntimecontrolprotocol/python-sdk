"""§9.6 / §13.5 — budget decrement, BUDGET_EXHAUSTED on next authorized op."""

from __future__ import annotations

from arcp import BudgetExhaustedError
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime


async def test_budget_decrement_and_authorize_failure(
    runtime: ARCPRuntime, client: ARCPClient
) -> None:
    async def spender(input_value, ctx):
        await ctx.metric({"name": "cost.fetch", "value": 0.70, "unit": "USD"})
        await ctx.metric({"name": "cost.fetch", "value": 0.40, "unit": "USD"})
        # Next op authorize after budget exhaust must raise.
        try:
            ctx.authorize("net.fetch", "https://example.com")
        except BudgetExhaustedError:
            return "blocked"
        return "passed"

    runtime.register_agent("spender", spender)
    handle = await client.submit(
        agent="spender",
        lease_request={
            "cost.budget": ["USD:1.00"],
            "net.fetch": ["https://example.com"],
        },
    )
    result = await handle.done
    assert result.result == "blocked"


async def test_negative_cost_metric_rejected(runtime: ARCPRuntime, client: ARCPClient) -> None:
    captured: list[Exception] = []

    async def neg(input_value, ctx):
        try:
            await ctx.metric({"name": "cost.x", "value": -1, "unit": "USD"})
        except ValueError as e:
            captured.append(e)
        return "ok"

    runtime.register_agent("neg", neg)
    handle = await client.submit(agent="neg", lease_request={"cost.budget": ["USD:1.00"]})
    await handle.done
    assert len(captured) == 1
