# ARCP Python Examples — Build Plan

Status: Phase 0 in flight. This file is the running design log. Update it as decisions evolve, gaps surface, or scope shifts.

## Mission recap

Build eleven runnable, testable, well-documented Python applications that each pin a distinct surface of the Agent Runtime Control Protocol (ARCP, RFC-0001 v2). Every example runs offline against scripted fixtures by default and against real LLM providers and external services when API keys / service URLs are provided via environment variables. The examples are *the* reference documentation for the protocol: a reader of the RFC turns to them to ground each abstract section in something they can run, modify, and break.

The eleven examples are *not* a package. There is no `pyproject.toml`, no console-script entrypoint, no installable surface inside `examples/`. Each example is a directory of plain Python scripts run directly with `python examples/NN_name/main.py`, with dependencies declared in a single top-level `examples/requirements.txt`.

## One-paragraph summaries

1. **Sysops Agent** (`01_sysops/`) — Single-agent stdio runtime fronting an MCP server that exposes filesystem and shell tools. The agent receives a natural-language task ("summarize all Python files modified today"), plans tool calls, and each invocation goes through the §15.4 permission-challenge flow and gets a §15.5 lease scoped to the operation. `shell.execute` streams stdout/stderr as §11 `stream.chunk` envelopes of `kind: text`. *Primary:* §11 streams, §15 permissions, §15.5 leases. *Secondary:* §18 error taxonomy when a tool fails; §17.3 `tool.invocations` metric; §10 job lifecycle.

2. **Multi-Agent Research Squad** (`02_subagents/`) — Orchestrator + three specialist runtimes (OpenAI, Gemini, Claude) over WebSocket with bearer auth. The orchestrator decomposes a research task and uses §14 `agent.delegate` to fan out to specialists, propagating a shared `trace_id` and inherited permissions. It subscribes (§13) to each specialist's session and stitches the timeline, then emits a §17.3 `cost.usd` and `tokens.used` rollup at completion. *Primary:* §14 delegate, §17.3 metric rollups, §13 subscriptions. *Secondary:* §7 capability negotiation; §17.1 distributed tracing.

3. **Code-Review Veto** (`03_code_review_veto/`) — WebSocket runtime with `signed_jwt` auth running a Claude-backed code-review agent that walks a refactor plan. Risky changes emit §12.2 `human.choice.request` with `[approve, deny, request_changes]`, sent at `priority: critical` (§6.5) via a fan-out relay to ntfy + Telegram + email — first-response-wins, schema-validated against the request's `response_schema`. Unresponded requests auto-fail per §12.4 `expires_at`. *Primary:* §12.2 choice request, §15.4 permission challenge, §6.5 priority.

4. **SDR Control Plane** (`04_sdr_extension/`) — GLM-4 agent over stdio with bearer auth driving an extension namespace `arcpx.sdr.v1`. The runtime advertises the extension in §7 capabilities; messages like `arcpx.sdr.frequency.tune`, `arcpx.sdr.spectrum.snapshot`, `arcpx.sdr.demodulate.start/stop` are registered with the SDK's `ExtensionRegistry`. A non-supporting client gets `nack UNIMPLEMENTED` per §21.3; a supporting client tunes, snapshots synthetic spectrum, demodulates briefly. *Primary:* §21 extensions, §7 capability negotiation.

5. **Tiered Support Handoff** (`05_tiered_handoff/`) — Two runtimes (Tier 1: Gemini Flash, Tier 2: Claude Opus) over WebSocket with `signed_jwt` + identity claims (§8.3). When Tier 1 escalates, it issues §14 `agent.handoff` carrying the Tier 2 identity for the client to verify. Tier 2 resumes from the session history and continues the conversation. Cost rollup attributes spend to each tier via §17.3 `cost.usd` with `dims.tier` and `dims.model`. *Primary:* §14 handoff, §8.3 runtime identity, §17.3 cost.

6. **DB Admin Permissions** (`06_db_admin_permissions/`) — GPT-4 agent over WebSocket with `signed_jwt` + LDAP-backed group resolution. Tools (read/write/schema-alter) front a SQLite database (self-contained, no Postgres). Reads proceed directly under a `db.read.*` permission with a routine lease; writes require human approval (relay); schema changes require §15.6 `trust.elevate.privileged`. Group `cn=db-readonly` resolves to `db.read.*`; `cn=db-writers` adds `db.write.*`; `cn=db-admins` adds elevation. Lease lifecycle (grant → refresh → revoke → expire) is fully exercised. *Primary:* §8 auth, §15 permissions, §15.5 leases, §15.6 elevation.

7. **Triple-Sink Observability** (`07_triple_sink_observability/`) — A small mixed Anthropic + OpenAI workload runs in one runtime. Three subscriber clients (`langfuse_sink`, `datadog_sink`, `otel_sink`) each subscribe (§13) with a different filter and route events to a different observability sink. Langfuse gets §11.4 thoughts, structured logs, and per-step metrics. Datadog gets operational metrics and `job.failed`. OTel gets `trace.span` events exported via OTLP. The test asserts no leakage — `kind: thought` never appears in Datadog. *Primary:* §13 subscriptions, §17 observability, §17.3.1 standard metric names.

8. **OpenClaw Skill Orchestrator** (`08_openclaw_orchestrator/`) — Claude orchestrator over WebSocket (Tailscale in real mode) with `signed_jwt` + Authentik. Connects to OpenClaw (or `MockOpenClaw`) and discovers four skills (breaking-news monitor, YouTube DVR, morning-briefing, Pakman fetcher) as MCP tools. Runs a morning-briefing workflow: subscribes (§13) to the breaking-news skill, delegates (§14) parallel DVR jobs, stitches a digest. The workflow uses §19 resume to recover from mid-run disconnects, with §17 events flowing through the whole chain. *Primary:* §14 delegate, §19 resume, §17 observability.

9. **LiteLLM Marketplace** (`09_litellm_marketplace/`) — A runtime exposing one tool, `llm.complete`, that takes `(prompt, budget_usd, max_latency_ms, required_capabilities)` and selects an LLM through LiteLLM. Selection is model-aware: cheap-fast for trivial prompts, capable for hard ones, with fallback on `RATE_LIMITED`. Failures map to canonical §18 codes: `RESOURCE_EXHAUSTED` (budget too low), `UNAVAILABLE` with `retryable=True` (all providers down), `DEADLINE_EXCEEDED`. The §17.3 `tokens.used` metric carries `dims.model` for attribution. *Primary:* §17.3 standard metrics, §18 retryable errors.

10. **Durable Research Pipeline** (`10_durable_research/`) — Anthropic Sonnet agent running a long research workflow over WebSocket with bearer auth. Emits §10.3 `job.heartbeat` on a 5-second cadence with monotonically increasing `sequence`, takes §10 `job.checkpoint` events at milestones, and writes a knowledge-graph artifact via §16 `artifact.put` returning `artifact.ref`. Mid-job, a test severs the TCP connection; the client reconnects with §19 `resume` and the runtime delivers backfilled events up to the cut point, then continues live. *Primary:* §19 resume, §16 artifacts, §10.3 heartbeats.

11. **Reasoning Stream Mirror** (`11_reasoning_mirror/`) — Two processes: an agent runtime on stdio (OpenAI o-series or DeepSeek R1) emits §11.4 `stream.chunk kind: thought`, with some chunks marked `redacted: true`. An observer runtime on WebSocket subscribes (§13) and renders the thought stream. The observer artificially throttles its render queue; the runtime emits §11.2 `backpressure` with a `desired_rate_per_second`, drops low-priority thought chunks first (§6.5), and the observer reports what it received vs what the agent emitted. Auth is `none` (negotiated anonymous, §8.2). *Primary:* §11.4 thought streams, §11.2 backpressure, §13 observer subscriptions.

## Shared component dependency graph

```
                     ┌───────────────────────────────────┐
                     │            _shared/               │
                     │                                   │
   providers/  ──────┼─►  used by 1, 2, 3, 4, 5, 6, 7,   │
                     │                  8, 9, 10, 11     │
                     │                                   │
   destinations/ ────┼─►  used by 3 (primary), 6 (write  │
                     │                  approvals)       │
                     │                                   │
   auth/         ────┼─►  used by 3, 5, 6, 8 (jwt),      │
                     │                  6 (ldap)         │
                     │                                   │
   observability/────┼─►  used by 7 (primary), partial   │
                     │                  use in 2, 6, 10  │
                     │                                   │
   openclaw/    ────┼─►  used by 8                       │
                     │                                   │
   transport/   ────┼─►  used by EVERY example test      │
                     │                                   │
                     └───────────────────────────────────┘
```

Build order respects this graph: Phase 1 lands all shared modules in one pass before any example consumes them.

## External services touched (fixture mode + real mode)

| Service | Used by | Fixture | Real-mode gate |
|---|---|---|---|
| Anthropic API | 1, 2, 3, 5, 7, 8, 10 | `ScriptedProvider` with canned messages | `ARCP_EXAMPLES_ANTHROPIC_API_KEY` |
| OpenAI API | 2, 6, 7, 9, 11 | `ScriptedProvider` | `ARCP_EXAMPLES_OPENAI_API_KEY` |
| Google Gemini | 2, 5 | `ScriptedProvider` | `ARCP_EXAMPLES_GEMINI_API_KEY` |
| Z.ai GLM | 4 | `ScriptedProvider` | `ARCP_EXAMPLES_ZHIPU_API_KEY` |
| DeepSeek | 11 | `ScriptedProvider` | `ARCP_EXAMPLES_DEEPSEEK_API_KEY` |
| LiteLLM proxy | 9 | `ScriptedProvider` impersonating LiteLLM responses | `LITELLM_PROXY_URL` |
| ntfy.sh | 3 | `ScriptedDestination` | `NTFY_URL`, `NTFY_TOPIC` |
| Telegram | 3 | `ScriptedDestination` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| SMTP / email | 3 | `ScriptedDestination` | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_TO` |
| LDAP | 6 | `MockLDAP` reading `ldap_directory.yaml` | `OPENLDAP_URL`, `OPENLDAP_BIND_DN`, `OPENLDAP_BIND_PW` |
| JWT signing | 3, 5, 6, 8 | ed25519 keypair generated at test session start | `ARCP_EXAMPLES_JWT_PRIVATE_KEY` (PEM path) and `..._PUBLIC_KEY` |
| Langfuse | 7 | `RecordingLangfuse` (append events to list) | `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` |
| Datadog | 7 | `RecordingDatadog` (buffer metric submissions) | `DD_API_KEY`, `DD_SITE` |
| OTel collector | 7 | `InMemorySpanExporter` (built into `opentelemetry-sdk`) | `OTEL_EXPORTER_OTLP_ENDPOINT` |
| OpenClaw | 8 | `MockOpenClaw` exposing four canned skills | `OPENCLAW_URL`, optional `AUTHENTIK_TOKEN` |
| RTL-SDR hardware | 4 | Fake spectrum generator (synthetic IQ data) | install `pyrtlsdr` and have hardware |

Every fixture path is the default. Real-mode tests are guarded by `pytest.mark.skipif(os.getenv(...) is None, reason="real-mode only")`.

## Provider / destination / auth fixture API sketches

### Provider Protocol

```python
class Message(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: NotRequired[str]
    tool_call_id: NotRequired[str]

class ToolDef(TypedDict):
    name: str
    description: str
    input_schema: dict[str, Any]

@dataclass
class CompletionResult:
    text: str
    tool_calls: list[ToolCall]
    finish_reason: Literal["stop", "tool_use", "length", "content_filter"]
    usage: Usage  # {input_tokens, output_tokens, cache_read, cache_write}
    model: str

@dataclass
class StreamChunk:
    kind: Literal["text", "thought", "tool_call_delta", "stop"]
    content: str
    redacted: bool = False
    tool_call: ToolCall | None = None
    usage_delta: Usage | None = None

class Provider(Protocol):
    name: str
    model: str

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDef] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> CompletionResult: ...

    def stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[StreamChunk]: ...
```

`get_provider("scripted:01_sysops")` reads `examples/01_sysops/fixtures/scripted.yaml`, returns a `ScriptedProvider` that matches the next incoming `messages[-1].content` against patterns and yields the configured response.

### Destination Protocol

```python
class Destination(Protocol):
    name: str
    supports_actions: bool

    async def send(self, request: HumanInputRequest) -> None: ...
    async def cancel(self, correlation_id: MessageId, reason: str) -> None: ...
    def receive(self) -> AsyncIterator[HumanInputResponse]: ...
```

`Relay` fans `send` to N destinations, races `receive` with `asyncio.wait(..., return_when=FIRST_COMPLETED)`, cancels losers with the originating `correlation_id`, validates the chosen response against the request's `response_schema`.

### Auth fixtures

- `_shared.auth.jwt_keys.session_keypair()` — pytest-fixture-scoped ed25519 keypair; deterministic seed under `ARCP_EXAMPLES_JWT_SEED` for golden tests.
- `_shared.auth.ldap_mock.MockLDAP(directory_yaml)` — synchronous in-memory LDAP. Implements only the subset we need: `search(base, filter)` returning a list of entries with `cn`, `memberOf`, `mail`. Real adapter `LDAPClient` in `ldap_real.py` uses `ldap3` against `OPENLDAP_URL`.

## Open RFC questions / chosen interpretations

1. **Heartbeat interval defaults.** RFC §10.3 specifies "≤ heartbeat_interval_seconds (default 30s)". Example 10 uses 5s to keep tests fast. Documented in the example README.
2. **`priority` ordering across streams.** §6.5 says shed lower-priority first, but never reorder within a stream. Example 11's backpressure logic drops thought chunks of `priority: low` before text chunks of `priority: normal`. We never drop chunks within the same stream.
3. **Extension namespace examples.** Example 4 uses `arcpx.sdr.v1` (no vendor). Any example-specific custom messages live under `arcpx.examples.<NN_name>.v1`. Bare `x-` is forbidden per §21.1.
4. **Idempotency vs envelope id.** §6.4 distinguishes `id` (transport) and `idempotency_key` (logical). Examples 3 (relay) and 9 (LiteLLM) supply `idempotency_key` for human responses and LLM calls respectively, so retries are safe.
5. **Anonymous auth in example 11.** §8.2 allows `none`. We still issue a session.accepted and treat the observer as `principal: "anonymous"` so subscription filters still authorize against trace_id.

## Phase plan

| Phase | Scope | Gate |
|---|---|---|
| 0 | Plan + skeleton + requirements + ruff + conftest + .env.example + docker-compose | Empty pytest run is clean; ruff + pyright clean |
| 1 | All of `_shared/` (providers, destinations, auth, observability, openclaw, transport) | `_shared/` ≥ 90% coverage, gate clean |
| 2 | Example 01 sysops | Runs scripted, ≥85% coverage on `01_sysops/`, README complete |
| 3 | Examples 10, 11 (protocol-only) | Resume + backpressure tests pass; ≥85% on each |
| 4 | Examples 2, 5 (multi-agent) | trace_id continuity asserted across runtimes; ≥85% |
| 5 | Example 3 (HITL) | All three response paths tested; expiration triggers cancellation |
| 6 | Example 4 (extension) | Unsupported-extension → nack UNIMPLEMENTED; supported → round-trip |
| 7 | Example 6 (DB admin) | LDAP groups → permissions, full lease lifecycle |
| 8 | Example 7 (observability) | Three sinks, no leakage |
| 9 | Example 9 (LiteLLM) | Three failure paths exercised |
| 10 | Example 8 (OpenClaw) | Skill discovery + delegate + resume |
| 11 | Cross-example tests + docs | All eleven `main.py` run scripted in one pytest |

## Cross-cutting risks

- **`structlog` vs `print`.** The prompt forbids `print()` outside `main.py` entrypoints. `structlog` is configured in `_shared/__init__.py` to write to stdout in `console` renderer for human-friendliness.
- **Pyright strict + Pydantic v2.** SDK is Pydantic v2; example code stays in lockstep. JSON trust-boundary `Any` is permitted (parsing arbitrary YAML fixtures and incoming JSON-RPC dicts), parsed to typed models immediately after.
- **Test parallelism.** Pytest is run with `-q`; no `-n auto`. Examples that spawn subprocesses (11) must clean up reliably.
- **Coverage measurement.** Coverage is run with `--cov=examples` so both `_shared/` and `NN_name/` count toward the floor. Test files themselves are excluded via `.coveragerc` if needed.
- **Real-mode tests in CI.** All real-mode tests are gated; CI invokes pytest without any of the relevant env vars and they skip cleanly.

## Future work (deferred)

- Browser-based observer UI for example 11 (out of scope per prompt; we emit a CLI render).
- Kubernetes manifests / Terraform — out of scope.
- WASM sandbox for example 4 SDR hardware adapter — out of scope.
- Real OpenClaw deployment automation — README documents Tailscale + Authentik + Spruce; we do not script it.
- Cross-language interop tests with the other ten SDK repos under `/Users/nficano/code/arpc/` — out of scope.

## Status log

- **Phase 0 (in progress):** Skeleton created, requirements drafted, plan committed. Next: confirm gate runs clean.
