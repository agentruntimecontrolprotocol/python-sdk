# Recipes

Copy-paste examples for common ARCP patterns. Each recipe is a self-contained, runnable Python file.

## Hosting

| Recipe | Description |
|---|---|
| [Host with ASGI](recipes/host-asgi.md) | Serve an `ARCPRuntime` via FastAPI / Starlette |
| [Host with aiohttp](recipes/host-aiohttp.md) | Serve an `ARCPRuntime` via aiohttp |
| [Host with stdio](recipes/stdio.md) | Subprocess / MCP-compatible stdio transport |
| [Host with OpenTelemetry](recipes/host-tracing.md) | Add distributed tracing to a runtime |

## Jobs

| Recipe | Description |
|---|---|
| [Submit and stream](recipes/submit-and-stream.md) | Submit a job and stream result chunks |
| [Cancel a job](recipes/cancel.md) | Cancel an in-flight job |
| [Idempotent retry](recipes/idempotent-retry.md) | Resubmit with idempotency key |
| [List jobs](recipes/list-jobs.md) | Query all jobs in a session |

## Events

| Recipe | Description |
|---|---|
| [Progress](recipes/progress.md) | Emit progress updates from an agent |
| [Result chunks](recipes/result-chunk.md) | Stream result fragments |
| [Heartbeats](recipes/heartbeat.md) | Keep long-running jobs alive |
| [Subscribe](recipes/subscribe.md) | Subscribe to events from outside the submit call |
| [Ack / backpressure](recipes/ack-backpressure.md) | Explicit event acknowledgement |

## Leases

| Recipe | Description |
|---|---|
| [Cost budget](recipes/cost-budget.md) | Cap spend with `max_cost_usd` |
| [Lease expires-at](recipes/lease-expires-at.md) | Cap wall time with an absolute timestamp |
| [Lease violation](recipes/lease-violation.md) | Handle `LeaseExceededError` |
| [Email vendor leases](recipes/email-vendor-leases.md) | Pass vendor-specific lease fields via `x-*` extensions |

## Auth and security

| Recipe | Description |
|---|---|
| [Custom auth](recipes/custom-auth.md) | Implement a custom bearer verifier |
| [Provisioned credentials](recipes/provisioned-credentials.md) | Inject per-job credentials from a secret store |
| [Delegate](recipes/delegate.md) | Agent-to-agent delegation chain |

## Advanced

| Recipe | Description |
|---|---|
| [Agent versions](recipes/agent-versions.md) | Register and pin to specific agent versions |
| [Stream resume](recipes/resume.md) | Resume an interrupted event stream |
| [MCP skill](recipes/mcp-skill.md) | Expose an MCP tool as an ARCP agent |
| [Multi-agent budget](recipes/multi-agent-budget.md) | Coordinate cost budgets across a chain of agents |
