"""§9.6 — upstream budget errors translate to BUDGET_EXHAUSTED."""

from __future__ import annotations

import pytest

from arcp import BudgetExhaustedError
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, UpstreamBudgetExhausted


async def test_upstream_budget_error_emits_budget_exhausted(
    runtime: ARCPRuntime,
    client: ARCPClient,
) -> None:
    async def agent(input_value, ctx):
        raise UpstreamBudgetExhausted("gateway budget exhausted")

    runtime.register_agent("budget-gateway", agent)
    handle = await client.submit(
        agent="budget-gateway",
        lease_request={"cost.budget": ["USD:1.00"]},
    )

    with pytest.raises(BudgetExhaustedError):
        await handle.done
