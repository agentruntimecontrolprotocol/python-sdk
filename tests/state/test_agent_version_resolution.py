"""§7.5 / §13.7 — agent version resolution."""

from __future__ import annotations

import pytest

from arcp import AgentVersionNotAvailableError
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime


async def test_bare_with_default_resolves(runtime: ARCPRuntime, client: ARCPClient) -> None:
    async def agent(input_value, ctx):
        return ctx.agent_ref

    runtime.register_agent_version("code-refactor", "2.0.0", agent)
    runtime.set_default_agent_version("code-refactor", "2.0.0")
    handle = await client.submit(agent="code-refactor")
    result = await handle.done
    assert result.result == "code-refactor@2.0.0"


async def test_pinned_version_resolves(runtime: ARCPRuntime, client: ARCPClient) -> None:
    async def agent_v1(input_value, ctx):
        return "v1"

    async def agent_v2(input_value, ctx):
        return "v2"

    runtime.register_agent_version("code-refactor-b", "1.0.0", agent_v1)
    runtime.register_agent_version("code-refactor-b", "2.0.0", agent_v2)
    handle = await client.submit(agent="code-refactor-b@1.0.0")
    result = await handle.done
    assert result.result == "v1"


async def test_missing_version_raises(runtime: ARCPRuntime, client: ARCPClient) -> None:
    async def agent(input_value, ctx):
        return "ok"

    runtime.register_agent_version("ver-c", "2.0.0", agent)
    with pytest.raises(AgentVersionNotAvailableError):
        await client.submit(agent="ver-c@3.0.0")
