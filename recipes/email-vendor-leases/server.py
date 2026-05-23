"""email-vendor-leases — Claude tool-use loop with a lease that denies send_reply.

A triage agent receives an "inbox check" task with a lease that grants
read-only tools but NOT send_reply. Claude reads each message, emits a
vendor-extension event per parsed message so dashboards can render
them specially, and eventually decides one needs a reply. When it
tries to call send_reply the lease check denies it; Claude observes
the PERMISSION_DENIED tool_result and degrades to drafting the reply
for human review.

Highlights: §13.4 lease violation as a *recoverable* tool_result error
(not session-fatal), §15 / §8.2 x-vendor.* event-kind namespace, and
a realistic Claude tool-use loop that handles a deny without crashing.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import anthropic

from arcp import PermissionDeniedError, RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7900"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")

TOOLS = [
    {
        "name": "inbox_list",
        "description": "List recent unread messages.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "inbox_read",
        "description": "Read one message by id.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "name": "send_reply",
        "description": "Send a reply to a message.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}, "body": {"type": "string"}},
            "required": ["id", "body"],
        },
    },
]

# stand-in inbox so the recipe is self-contained — swap for IMAP/Gmail in real use
INBOX = {
    "m1": {"id": "m1", "from": "ops@acme.dev", "subject": "Status", "body": "All quiet.", "urgency": "low"},
    "m2": {"id": "m2", "from": "ceo@acme.dev", "subject": "Outage!", "body": "Site is down — fix asap.", "urgency": "high"},
}


async def run_tool(name: str, args: dict[str, Any]) -> Any:
    if name == "inbox_list":
        return [{"id": m["id"], "subject": m["subject"], "from": m["from"]} for m in INBOX.values()]
    if name == "inbox_read":
        return INBOX[args["id"]]
    raise RuntimeError(f"tool {name} should have been denied before reaching run_tool")


async def triage_agent(_input: dict, ctx: JobContext) -> dict:
    client = anthropic.AsyncAnthropic()
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": "Triage my inbox. Read each unread message and reply to anything urgent.",
        }
    ]

    # tool-use loop: Claude proposes a tool call, we authorize against the
    # lease, run it (or surface a denial), feed the result back, repeat.
    while True:
        turn = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )

        if turn.stop_reason == "end_turn":
            text = next((b.text for b in turn.content if b.type == "text"), "")
            return {"drafted_reply": text, "sent": False}

        # append the assistant turn so the next call has full context
        messages.append({"role": "assistant", "content": [b.model_dump() for b in turn.content]})
        tool_results: list[dict[str, Any]] = []

        for block in turn.content:
            if block.type != "tool_use":
                continue

            await ctx.tool_call({"tool_call_id": block.id, "tool": block.name, "args": block.input})

            try:
                # the lease grants tool.call only for the read-only tools; the
                # send_reply pattern is absent so this raises PermissionDenied
                ctx.authorize("tool.call", block.name)
            except PermissionDeniedError as err:
                # surface the denial on the ARCP stream as a recoverable error...
                await ctx.tool_result(
                    {
                        "tool_call_id": block.id,
                        "error": {"code": err.code, "message": str(err), "retryable": False},
                    }
                )
                # ...and hand it to Claude as the tool result so the model can
                # recover gracefully — lease violations are not session-fatal
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"denied: {err}",
                        "is_error": True,
                    }
                )
                continue

            result = await run_tool(block.name, block.input)
            if block.name == "inbox_read":
                # vendor-extension event — dashboards that recognise the
                # x-vendor.acme.* namespace render parsed metadata specially
                await ctx.job.emit_event(
                    "x-vendor.acme.email.parsed",
                    {
                        "message_id": result["id"],
                        "from": result["from"],
                        "subject": result["subject"],
                        "urgency": result["urgency"],
                    },
                )
            await ctx.tool_result({"tool_call_id": block.id, "output": result})
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": str(result)}
            )

        messages.append({"role": "user", "content": tool_results})


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="email-triage", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("triage", triage_agent)
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
