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
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from arcp import (
    ARCPClient,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp.runtime import ARCPRuntime, StaticBearerVerifier
from arcp._runtime.job import JobContext


def make_mcp_skill(tool_name: str, server_params: StdioServerParameters):
    """Return an ARCP agent function that proxies *tool_name* on the MCP server."""

    async def agent(arguments: dict[str, Any], ctx: JobContext) -> dict[str, Any]:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

        async with ctx.stream_result() as stream:
            for content_block in result.content:
                if content_block.type == "text":
                    await stream.write(content_block.text)
                else:
                    await stream.write(content_block.model_dump_json())
        return {"tool": tool_name}

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
    runtime=RuntimeInfo(name="mcp-bridge", version="1.0.0"),
    bearer=StaticBearerVerifier({"secret": "principal-1"}),
)
runtime.register_agent("read_file", make_mcp_skill("read_file", fs_server))
```

## Client

```python
import asyncio
from arcp import ARCPClient, ClientInfo


async def main() -> None:
    asyncio.create_task(runtime.accept(server_transport))
    client = ARCPClient(
        client=ClientInfo(name="mcp-caller", version="1.0.0"),
        token="secret",
    )
    await client.connect(client_transport)
    handle = await client.submit(
        agent="read_file",
        input={"path": "/tmp/hello.txt"},
    )
    async for chunk in handle.chunks():
        # `chunk` is the result_chunk wire body; `data` is the decoded text
        # or base64 bytes (per `encoding`).
        print(chunk.get("data"))
    await handle.done
    await client.close()


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
to a `job.error` envelope with an appropriate error code (spec
[§12](https://arcp.dev/spec/v1.1#section-12)).  You can also catch MCP errors
explicitly and re-raise as typed ARCP exceptions:

```python
from mcp.shared.exceptions import McpError
from arcp import InvalidRequestError

try:
    result = await session.call_tool(tool_name, arguments)
except McpError as exc:
    raise InvalidRequestError(str(exc)) from exc
```

## Related

- [Vendor extensions guide](../guides/vendor-extensions.md)
- [Errors guide](../guides/errors.md)
- [Result chunk recipe](result-chunk.md)
- [Submit and stream recipe](submit-and-stream.md)
