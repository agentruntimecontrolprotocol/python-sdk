# Recipes

Composed ARCP features wired around a real LLM workload. Unlike the
single-feature [`examples/`](../examples/) — which use toy agents (echo,
cost-counter, slow timer) — each recipe is a complete end-to-end shape
with an actual provider SDK driving the agent.

## [multi-agent-budget/](multi-agent-budget/) — OpenAI

The planner decomposes a question into sub-questions and delegates each
to a worker carrying a budget slice carved from its own remaining cap.
After each grant the planner emits a `cost.delegate` metric on itself
so the runtime's subset check at the next delegate sees an honest
remaining balance. Workers that overspend trip `BUDGET_EXHAUSTED`;
sub-questions that no longer fit are skipped before the delegate.

## [email-vendor-leases/](email-vendor-leases/) — Claude

A triage agent runs Claude through a tool-use loop with three tools, but
the lease grants only the two read-only ones. When the model proposes
`send_reply` the agent's `ctx.authorize("tool.call", ...)` raises
`PermissionDeniedError` and feeds the denial back to Claude, which
observes the deny and returns a drafted-but-unsent reply. Each
`inbox_read` also emits an `x-vendor.acme.email.parsed` event so
dashboards recognising the namespace can render parsed metadata
specially.

## [stream-resume/](stream-resume/) — GLM-5

The writer pipes GLM-5's streaming deltas into `ctx.stream_result()`,
batching ~200 chars per `result_chunk` envelope. Every envelope lands in
the runtime's `EventLog` under a monotonic `event_seq`. The client drops
the transport mid-stream, opens a fresh session with `client.resume()`,
and the runtime replays every envelope past the cutoff so reassembly
completes seamlessly across the gap.

## [mcp-skill/](mcp-skill/) — MCP bridge

An MCP server fronts the [multi-agent-budget](multi-agent-budget/)
planner so any MCP host (Claude Code, Cursor, Desktop) can call it as a
single `research` tool. The bridge keeps one long-lived ARCP session;
each MCP tool invocation submits a fresh planner job and returns the
terminal result as the tool's text response. A Claude Code skill at
[skills/research/SKILL.md](mcp-skill/skills/research/SKILL.md) tells the
model when to reach for the tool.

## Running

Each recipe pairs a server and a client. Open two terminals:

```
python recipes/<name>/server.py    # terminal 1
python recipes/<name>/client.py    # terminal 2
```

Provider SDKs (`anthropic`, `openai`, `mcp`) are not pinned in
`pyproject.toml` because they are not core dependencies — install
whichever ones the recipe you want to run needs.
