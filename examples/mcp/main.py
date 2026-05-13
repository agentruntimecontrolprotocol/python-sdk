"""ARCP runtime fronting an MCP server (RFC §20).

MCP describes capabilities; ARCP operationalizes them. This bridge
translates inbound ARCP `tool.invoke` envelopes into MCP `call_tool`
calls against an upstream MCP server, and emits the ARCP job
lifecycle back to the calling client.

  ARCP client ──tool.invoke──> bridge ──call_tool──> MCP server
  ARCP client <─job.{accepted,started,completed,failed}─ bridge
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from mcp import ClientSession  # pyright: ignore[reportMissingImports]
from mcp.client.stdio import (
    stdio_client,  # pyright: ignore[reportMissingImports]
)

from arcp import ARCPError, Envelope, ErrorCode, new_message_id

from .upstream import upstream_params  # MCP server invocation

# Per RFC §20:
#   MCP tool schema -> ARCP capability  (advertised at session.accepted)
#   MCP tool call   -> ARCP job
#   MCP resource    -> ARCP stream of kind: event  (delegated to MCP)


async def advertise_from_mcp(mcp: ClientSession) -> list[str]:
    """MCP `tools/list` → namespaced ARCP capability extensions.

    Each upstream tool surfaces as `arcpx.mcp.tool.<name>.v1` so
    clients can negotiate which tools they require at session open.
    """
    listed = await mcp.list_tools()
    return [f"arcpx.mcp.tool.{t.name}.v1" for t in listed.tools]


async def call_via_mcp(
    mcp: ClientSession, *, tool: str, arguments: dict[str, object]
) -> dict[str, object]:
    """Translate ARCP `tool.invoke.payload` into MCP `call_tool`.

    MCP returns a list of typed content blocks; we flatten to a JSON-
    serializable dict for the ARCP `tool.result` / `job.completed`
    payload. MCP errors become canonical ARCP error codes.
    """
    try:
        result = await mcp.call_tool(tool, arguments=arguments)
    except Exception as exc:
        raise ARCPError(ErrorCode.INTERNAL, str(exc)) from exc

    if result.isError:
        text = "\n".join(getattr(c, "text", "") for c in result.content)
        # MCP doesn't carry a typed error code; FAILED_PRECONDITION is
        # the right canonical mapping for "tool ran, said no".
        raise ARCPError(ErrorCode.FAILED_PRECONDITION, text or "tool error")

    return {"content": [c.model_dump() for c in result.content]}


SendEnvelope = Callable[[Envelope], Awaitable[None]]


async def handle_invoke(
    send: SendEnvelope,
    *,
    mcp: ClientSession,
    request: Envelope,
) -> None:
    """One inbound ARCP `tool.invoke` → MCP call → ARCP job lifecycle."""
    job_id = f"job_{new_message_id()[-10:]}"

    await send(
        Envelope(
            id=new_message_id(),
            type="job.accepted",
            correlation_id=request.id,
            job_id=job_id,
            payload={"job_id": job_id, "state": "accepted"},
        )
    )
    await send(
        Envelope(
            id=new_message_id(),
            type="job.started",
            job_id=job_id,
            payload={"job_id": job_id},
        )
    )

    try:
        result = await call_via_mcp(
            mcp,
            tool=str(request.payload["tool"]),
            arguments=dict(request.payload.get("arguments", {})),
        )
    except ARCPError as exc:
        await send(
            Envelope(
                id=new_message_id(),
                type="job.failed",
                job_id=job_id,
                payload=exc.to_payload(),
            )
        )
        return

    await send(
        Envelope(
            id=new_message_id(),
            type="job.completed",
            job_id=job_id,
            payload={"result": result},
        )
    )


async def run_bridge(send: SendEnvelope, inbound) -> None:
    """Wire one MCP session as the upstream for one ARCP runtime."""
    async with (
        stdio_client(upstream_params()) as (read, write),
        ClientSession(read, write) as mcp,
    ):
        await mcp.initialize()
        extensions = await advertise_from_mcp(mcp)
        # In production this list would feed `Capabilities.extensions`
        # at the runtime's `session.accepted` so clients negotiate
        # exactly the MCP tools they expect to use.
        print(f"bridged: {extensions}")

        async for envelope in inbound:  # the runtime's inbound queue
            if envelope.type == "tool.invoke":
                await handle_invoke(send, mcp=mcp, request=envelope)


async def main() -> None:
    # Production version: instantiate an `arcp.ARCPRuntime`, point its
    # tool-invoke handler at `handle_invoke`, and let the WebSocket
    # transport carry inbound envelopes from real ARCP clients. We
    # elide the runtime wiring (symmetric with examples in
    # arcp.runtime.server) so this file stays focused on the §20
    # translation between protocols.
    send: SendEnvelope = ...  # bound to the runtime's outbound channel
    inbound = ...  # async iterator of inbound envelopes
    await run_bridge(send, inbound)


if __name__ == "__main__":
    asyncio.run(main())
