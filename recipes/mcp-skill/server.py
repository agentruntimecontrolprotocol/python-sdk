"""mcp-skill — bridge an MCP `research` tool to the multi-agent-budget planner.

An MCP server that bridges to the multi-agent-budget runtime, exposing
the ARCP planner as a single `research` tool. The Claude Code skill in
skills/research/SKILL.md describes when to invoke the tool; this file
is the runtime bridge it ends up calling.

Highlights: the seam between MCP (model-side tool surface) and ARCP
(runtime-side agent execution). One long-lived ARCP session per MCP
process; each MCP tool call submits a fresh ARCP job through it. The
agent's eventual lease, cost cap, and delegation tree are entirely
ARCP concerns — MCP just sees one call in, one result out.

Run the multi-agent-budget server first, then point an MCP host at
this script.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7899"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> None:
    # one ARCP session for the lifetime of the bridge process. each MCP
    # tool call submits a new job through this session.
    arcp = ARCPClient(
        client=ClientInfo(name="mcp-bridge", version="1.0.0"),
        token=TOKEN,
        features=("cost.budget",),
    )
    transport = await WebSocketTransport.connect(URL)
    await arcp.connect(transport)

    mcp = Server("arcp-research-bridge")

    @mcp.list_tools()
    async def _list_tools() -> list[Tool]:
        # advertise one tool. the MCP host (Claude Code / Cursor / Desktop)
        # reads this schema and presents it to the model as a callable tool.
        return [
            Tool(
                name="research",
                description=(
                    "Decompose a research question into sub-questions and answer "
                    "each under a shared cost cap. Returns the plan, delegated "
                    "sub-questions, and any dropped for budget."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "budget_usd": {"type": "number", "default": 0.5},
                    },
                    "required": ["question"],
                },
            )
        ]

    @mcp.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        # tool invocation: forward into ARCP and shape the terminal result
        # back as an MCP tool response.
        if name != "research":
            raise ValueError(f"unknown tool: {name}")
        budget = float(arguments.get("budget_usd", 0.5))
        handle = await arcp.submit(
            agent="planner",
            input={"question": arguments["question"]},
            lease_request={
                "cost.budget": [f"USD:{budget:.2f}"],
                "tool.call": ["llm.complete"],
                "agent.delegate": ["worker"],
            },
        )
        result = await handle.done
        # MCP tool responses are an array of content blocks; here we emit a
        # single text block carrying the planner's JSON result.
        return [TextContent(type="text", text=json.dumps(result.result, indent=2))]

    # MCP servers typically speak stdio to their host process.
    async with stdio_server() as (read, write):
        await mcp.run(read, write, mcp.create_initialization_options())

    await arcp.close()


if __name__ == "__main__":
    asyncio.run(main())
