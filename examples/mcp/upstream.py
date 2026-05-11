"""Upstream MCP server invocation.

Real version parameterizes command, args, env via your config layer.
Reference servers from the modelcontextprotocol org publish under
`mcp-server-*` (filesystem, git, postgres, slack, ...).
"""

from __future__ import annotations

from mcp import StdioServerParameters


def upstream_params() -> StdioServerParameters:
    return StdioServerParameters(
        command="uvx",
        args=["mcp-server-filesystem", "/srv/data"],
    )
