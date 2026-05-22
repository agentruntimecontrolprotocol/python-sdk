# MCP Skill

This recipe shows how to wrap a [Model Context Protocol (MCP)](https://modelcontextprotocol.io)
tool as an ARCP agent so that any ARCP caller can invoke it without knowing
anything about MCP internals.

## Concept

MCP tools are invoked synchronously (request → response).  ARCP jobs are
streaming and asynchronous.  The adapter pattern here:

1. Receives a single-item ARCP input stream containing the tool call arguments.
2. Calls the MCP tool via the MCP Python SDK.
3. Streams the result back as an ARCP `result.chunk` event followed by job
   completion.

## Prerequisites

```bash
uv add arcp mcp
```

## Adapter

```python
import asyncio
import json
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from arcp import ARCPRuntime, JobContext
from arcp.auth import StaticBearerVerifier
from arcp.transport import pair_memory_transports


def make_mcp_skill(tool_name: str, server_params: StdioServerParameters):
    """Return an ARCP agent function that proxies *tool_name* on the MCP server."""

    async def agent(ctx: JobContext) -> None:
        # Collect arguments from the single-item input stream.
        args: dict[str, Any] = {}
        async for item in ctx.input_stream():
            args.update(item)

        # Connect to the MCP server and call the tool.
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)

        # Emit MCP result content as ARCP result chunks.
        for content_block in result.content:
            if content_block.type == "text":
                await ctx.emit_event(
                    "result.chunk",
                    {"text": content_block.text},
                )
            else:
                await ctx.emit_event(
                    "result.chunk",
                    {"data": json.loads(content_block.model_dump_json())},
                )

    agent.__name__ = f"mcp_{tool_name}"
    return agent


# ---------------------------------------------------------------------------
# Example: expose the MCP filesystem server's "read_file" tool as an ARCP agent
# ---------------------------------------------------------------------------

fs_server = StdioServerParameters(
    command="uvx",
    args=["mcp-server-filesystem", "/tmp"],
)

server_transport, client_transport = pair_memory_transports()

runtime = ARCPRuntime(
    transport=server_transport,
    auth=StaticBearerVerifier("secret"),
)
runtime.register_agent("read_file", make_mcp_skill("read_file", fs_server))
```

## Client

```python
from arcp import ARCPClient


async def main() -> None:
    async with ARCPClient(client_transport, token="secret") as client:
        handle = await client.submit(
            agent="read_file",
            input=[{"path": "/tmp/hello.txt"}],
        )

        async for event in handle.events():
            if event.kind == "result.chunk":
                print(event.data.get("text", event.data))

        await handle.done


import asyncio
asyncio.run(main())
```

## Registering multiple MCP tools

```python
TOOLS = ["read_file", "write_file", "list_directory"]

for tool in TOOLS:
    runtime.register_agent(tool, make_mcp_skill(tool, fs_server))
```

## Error propagation

If the MCP tool raises, the exception propagates naturally and ARCP converts it
to a `job.failed` event with an appropriate error code (spec
[§12](https://arcp.dev/spec/v1.1#section-12)).  You can also catch MCP errors
explicitly and re-raise as typed ARCP exceptions:

```python
from mcp.exceptions import McpError
from arcp.errors import AgentError

try:
    result = await session.call_tool(tool_name, args)
except McpError as exc:
    raise AgentError(str(exc)) from exc
```

## Related

- [Vendor extensions guide](../guides/vendor-extensions.md)
- [Errors guide](../guides/errors.md)
- [Result chunk recipe](result-chunk.md)
- [Submit and stream recipe](submit-and-stream.md)
