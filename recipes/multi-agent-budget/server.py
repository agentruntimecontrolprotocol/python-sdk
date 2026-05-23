"""multi-agent-budget — planner decomposes a question and delegates workers under a shared cap.

A research planner with a USD:0.50 budget decomposes a question and
delegates sub-questions to worker children. Each grant is sliced from
the planner's own remaining budget, so the cap effectively cascades
across the tree. Workers that overspend trip BUDGET_EXHAUSTED; the
planner skips sub-questions that no longer fit.

Highlights: §13.2 delegation + lease-subset enforcement at delegate
time, §9.6 cost.budget auto-decrement on `cost.*` metrics, and the
"debit-self-for-each-grant" pattern that turns ARCP's independent
per-job counters into a shared cascade.
"""

from __future__ import annotations

import asyncio
import json
import os
from decimal import Decimal

import openai

from arcp import ClientInfo, RuntimeInfo, WebSocketTransport, serve_websocket
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7899"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")
LOOPBACK = f"ws://127.0.0.1:{PORT}/arcp"

PHASES = ("gather", "analyze", "summarize")
GRANT_BY_DEPTH = {1: Decimal("0.05"), 2: Decimal("0.10"), 3: Decimal("0.15")}


async def planner(input: dict, ctx: JobContext) -> dict:
    client = openai.AsyncOpenAI()
    # decompose the question into sub-questions tagged with a depth score
    plan_resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Decompose into 5 sub-questions. JSON "
                    "{subQuestions:[{question,depth:1|2|3}]}. "
                    f"Q: {input['question']}"
                ),
            }
        ],
    )
    # charge the plan call against our own budget so the next subset check
    # (below, at each delegate) sees an honest "remaining"
    await ctx.metric({"name": "cost.completion", "value": 0.05, "unit": "USD"})
    plan = json.loads(plan_resp.choices[0].message.content or "{}")
    sub_questions = plan.get("subQuestions", [])

    # parent agents drive delegation via a loopback client so the child
    # inherits trace_id over the wire (see spec §13.2).
    parent = ARCPClient(
        client=ClientInfo(name="planner-loopback", version="1.0.0"),
        token=TOKEN,
        features=(),
    )
    transport = await WebSocketTransport.connect(LOOPBACK)
    delegated: list[dict] = []
    dropped: list[dict] = []
    try:
        await parent.connect(transport)
        for i, sq in enumerate(sub_questions):
            grant = GRANT_BY_DEPTH.get(sq.get("depth", 1), Decimal("0.05"))
            # skip if our remaining budget no longer fits this grant — the
            # runtime would reject it anyway via the subset check, but a
            # graceful pre-check gives the planner a chance to report it back
            remaining = ctx.budget.get("USD", Decimal("0"))
            if remaining < grant:
                dropped.append({"question": sq["question"], "reason": "budget"})
                continue

            child = await parent.submit(
                agent="worker",
                input=sq,
                lease_request={
                    "cost.budget": [f"USD:{grant:.2f}"],
                    "tool.call": ["llm.complete"],
                },
                trace_id=ctx.trace_id,
                parent_job_id=ctx.job_id,
            )
            await ctx.job.emit_event(
                "delegate",
                {"child_job_id": child.job_id, "agent": "worker", "delegate_id": f"del_{i}"},
            )
            delegated.append({"question": sq["question"], "grant": f"USD:{grant:.2f}"})
            # debit ourselves so the next iteration's pre-check (and the
            # runtime's subset check) reflect what we've already committed
            await ctx.metric({"name": "cost.delegate", "value": float(grant), "unit": "USD"})
    finally:
        await parent.close()

    return {"plan": sub_questions, "delegated": delegated, "dropped": dropped}


async def worker(input: dict, ctx: JobContext) -> dict:
    client = openai.AsyncOpenAI()
    # three phases against the worker's own per-job budget
    for phase in PHASES:
        # authorize trips BudgetExhausted once the counter ≤ 0; the runtime
        # converts the raise into a terminal job.error
        ctx.authorize("cost.budget", "USD")
        await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"{phase}: {input['question']}"}],
        )
        await ctx.metric({"name": "cost.completion", "value": 0.05, "unit": "USD"})
    return {"phases": list(PHASES)}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="research", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("planner", planner)
    runtime.register_agent("worker", worker)
    server = await serve_websocket(runtime.accept, host="127.0.0.1", port=PORT, path="/arcp")
    print(f"listening on {LOOPBACK}")
    try:
        await asyncio.Future()
    finally:
        server.close()
        await server.wait_closed()
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
