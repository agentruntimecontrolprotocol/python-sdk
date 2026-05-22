"""§9.7 — model.use lease authorization."""

from __future__ import annotations

from arcp import PermissionDeniedError
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime


async def test_authorize_model_match_succeeds(runtime: ARCPRuntime, client: ARCPClient) -> None:
    async def agent(input_value, ctx):
        ctx.authorize_model("tier-fast/cheap")
        return "ok"

    runtime.register_agent("model-agent", agent)
    handle = await client.submit(
        agent="model-agent",
        lease_request={"model.use": ["tier-fast/*"]},
    )

    result = await handle.done

    assert result.result == "ok"


async def test_authorize_model_miss_raises(runtime: ARCPRuntime, client: ARCPClient) -> None:
    async def agent(input_value, ctx):
        try:
            ctx.authorize_model("anthropic/claude-3-opus")
        except PermissionDeniedError:
            return "blocked"
        return "passed"

    runtime.register_agent("blocked-model-agent", agent)
    handle = await client.submit(
        agent="blocked-model-agent",
        lease_request={"model.use": ["tier-fast/*"]},
    )

    result = await handle.done

    assert result.result == "blocked"


async def test_lease_without_model_use_blocks(runtime: ARCPRuntime, client: ARCPClient) -> None:
    async def agent(input_value, ctx):
        try:
            ctx.authorize_model("tier-fast/cheap")
        except PermissionDeniedError:
            return "blocked"
        return "passed"

    runtime.register_agent("no-model-lease-agent", agent)
    handle = await client.submit(agent="no-model-lease-agent")

    result = await handle.done

    assert result.result == "blocked"
