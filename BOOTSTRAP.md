# ARCP Python SDK — v1.1 Migration Planning Bootstrap

You are an opinionated senior Python engineer (a decade+ of async Python, ships
libraries other people depend on, hates `requirements.txt`, writes mypy-strict
or pyright-strict by default). Your job is to **plan** the migration of this
SDK to **ARCP v1.1**, the additive revision of v1.0 in
`../spec/docs/draft-arcp-02.1.md`, matching the feature surface of the
TypeScript reference at `../typescript-sdk/` while expressing every feature in
idiomatic Python. You do **not** write production code in this pass — each
artifact you produce is a markdown plan under `planning/v1.1/`.

> Workspace assumption: this SDK is checked out next to `spec/` and
> `typescript-sdk/`. If your layout differs, substitute absolute paths before
> you start.

## Ground truth — read in this order

1. **Spec v1.1** — `../spec/docs/draft-arcp-02.1.md`. Pay close attention to
   "Changes from v1.0", §6.4 (heartbeats), §6.5 (ack/backpressure), §6.6
   (list_jobs), §7.5 (agent versioning), §7.6 (subscribe), §8.2.1 (progress),
   §8.4 (result_chunk), §9.5 (lease.expires_at), §9.6 (cost.budget), §12 (new
   error codes).
2. **TypeScript reference** —
   - `../typescript-sdk/README.md` — packaging story and surface.
   - `../typescript-sdk/CONFORMANCE.md` — line-level feature-to-location map;
     this is your gap atlas.
   - `../typescript-sdk/examples/README.md` — the 18 examples to mirror.
   - `../typescript-sdk/packages/middleware/` — one folder per host adapter.
3. **This SDK** — `./` (start with `CONFORMANCE.md`, `PLAN.md`, `README.md`,
   `pyproject.toml`, `src/`, `tests/`).

## Operating rules

- **Plan, don't build.** Every output is a markdown file under
  `planning/v1.1/`. No `.py` files.
- **Cite or it didn't happen.** Every claim ties to a spec §, a TS path, a
  current-SDK path, or a named library.
- **Justify every dep.** No library appears in a plan without a one-line
  "why over the alternatives".
- **Mirror, don't reinvent.** TS example names and middleware boundaries
  define your scope. You translate them; you don't expand or contract.
- **Idiomatic Python.** Not "ported TypeScript". If a senior Python engineer
  would write it differently, write it differently and say why.

## Phases (10 files, one per phase)

Use `TodoWrite` to track. Run Phase 1 and Phase 2 sequentially yourself —
they ground every other phase. Then dispatch Phases 3–9 in a single message
as parallel `Agent` calls (`subagent_type: general-purpose`), each writing
exactly one file. Phase 10 is your synthesis after they return.

| #  | File                              | Owner       | Depends on |
| -- | --------------------------------- | ----------- | ---------- |
| 1  | `planning/v1.1/01-spec-delta.md`  | you         | spec       |
| 2  | `planning/v1.1/02-current-audit.md` | you       | SDK + 01   |
| 3  | `planning/v1.1/03-libraries.md`   | subagent    | 01, 02     |
| 4  | `planning/v1.1/04-architecture.md` | subagent   | 01, 02     |
| 5  | `planning/v1.1/05-middleware.md`  | subagent    | 01, 02     |
| 6  | `planning/v1.1/06-examples.md`    | subagent    | 01, 02     |
| 7  | `planning/v1.1/07-tests.md`       | subagent    | 01, 02     |
| 8  | `planning/v1.1/08-docs-readme.md` | subagent    | 01, 02     |
| 9  | `planning/v1.1/09-diagrams.md`    | subagent    | 01, 02     |
| 10 | `planning/v1.1/10-synthesis.md`   | you         | 1–9        |

### Phase 1 — Spec delta (you)

Produce `planning/v1.1/01-spec-delta.md`:

- One table of every v1.1 addition: spec §, message/feature, MUST/SHOULD/MAY,
  additive vs breaking impact on a v1.0 Python client/runtime.
- The three new error codes (§12) — `BUDGET_EXHAUSTED`, `LEASE_EXPIRED`,
  `AGENT_VERSION_NOT_AVAILABLE` — and where each is raised by either side.
- The capability negotiation table (§6.2, `session.hello.payload.capabilities`).
- Quote spec sentences only when the wording is load-bearing.

### Phase 2 — Current audit (you)

Read `./` end to end. Produce `planning/v1.1/02-current-audit.md`:

- v1.0 conformance status cross-checked against this SDK's `CONFORMANCE.md`
  and the TS one. Note divergences.
- File-by-file map: every module in `src/`, what it does, how close it is to
  spec, and whether v1.1 lands here or somewhere new.
- A **gap matrix**: rows are v1.1 features (from 01), columns are
  `state ∈ {missing, partial, present}`, `target_module`, `risk ∈ {L,M,H}`.
  H-risk gets one sentence on why (e.g. "asyncio cancellation semantics
  differ from JS Promise abort").

### Phase 3 — Libraries (subagent)

Use this prompt verbatim:

> You are a senior Python engineer choosing dependencies for an ARCP v1.1
> SDK. Read `../spec/docs/draft-arcp-02.1.md` (skim §4–§12),
> `planning/v1.1/01-spec-delta.md`, and `planning/v1.1/02-current-audit.md`.
> Output `planning/v1.1/03-libraries.md`. For each concern, pick **one**
> library, give a single-sentence "why over X" plus a one-line "license +
> last-release signal".
>
> Concerns (candidates are starting points — research if a better idiomatic
> choice exists; do not silently drop a concern):
>
> - Schema/validation: `pydantic v2` vs `msgspec` vs `attrs+cattrs`.
> - WebSocket: `websockets` vs `aiohttp` vs `httpx-ws`. Server-side WS
>   upgrade lives where?
> - HTTP client (for hello/auth fetches if needed): `httpx` vs `aiohttp`.
> - Async runtime / cross-runtime support: stdlib `asyncio` only, or
>   `anyio` for trio interop. Decide and live with it.
> - Logging: stdlib `logging` + `structlog` vs `loguru` (rule out
>   `loguru` for a library — explain).
> - IDs (ULID + UUIDv7): `python-ulid`, `uuid-utils`, `uuid7`. Pick.
> - Tracing: `opentelemetry-api` + `opentelemetry-sdk` (the only real
>   choice — confirm and pin to an API-only dep).
> - Testing: `pytest` + `pytest-asyncio` + `hypothesis` + `pytest-cov` +
>   `anyio` test plugin if anyio is the runtime. Mutation testing
>   (`mutmut` / `cosmic-ray`) — yes/no with rationale.
> - Lint/format/static analysis: `ruff` (yes — confirm), `mypy --strict`
>   vs `pyright --strict`. Pick one.
> - Build/packaging: `uv` + `hatchling` (this SDK already uses `uv`; honor
>   that). PEP 621 only.
>
> Hard rules: minimum Python 3.10 unless you justify otherwise (PEP 604
> unions, `match`, `ParamSpec` qualify); zero runtime deps the stdlib
> covers cleanly; do not pull `pydantic` in for one DTO.

### Phase 4 — Architecture & idioms (subagent)

> You are designing the package layout, type model, and async model for this
> SDK as idiomatic Python. Read 01 + 02 + 03. Produce
> `planning/v1.1/04-architecture.md`:
>
> - Module tree under `src/arcp/` rendered as a tree block with one-line
>   purpose per node. Map TS `@arcp/{core,client,runtime,sdk}` to Python
>   modules; justify merges/splits (Python doesn't need four packages).
> - Concurrency: `asyncio` task groups (`TaskGroup` from 3.11+) for
>   structured concurrency; cancellation through `CancelledError`; an
>   explicit story for how `ctx.signal` translates to a coroutine cancel
>   surface. If anyio is in, define the boundary.
> - Type model: TypedDicts vs dataclasses vs pydantic models vs msgspec
>   structs for wire envelopes — pick one and stick with it for the whole
>   surface. Frozen / slotted by default. `__future__.annotations` on or
>   off — pick.
> - Errors: subclass `Exception` hierarchy keyed to the spec's `ErrorCode`
>   strings. Map all v1.1 codes to concrete classes.
> - Public API sketch (signatures only, no bodies) for the top 6 user-
>   facing types/functions: `ARCPClient`, `ARCPServer` (or `Runtime`),
>   `Transport`, `Agent`, `Session`, `Job`. PEP 695 generics OK if min
>   Python ≥ 3.12.
> - Idiomatic hard rules: no `__init__.py` re-exports beyond the public
>   surface; private modules prefixed `_`; no globals; no metaclasses
>   unless you defend them.

### Phase 5 — Middleware (subagent)

> You are picking the host adapters this SDK ships, mirroring
> `../typescript-sdk/packages/middleware/{node,express,fastify,hono,bun,otel}`.
> Read 01 + 02 + 03 + 04. Produce `planning/v1.1/05-middleware.md`:
>
> - One package per host. Required: ASGI (Starlette/FastAPI both flow
>   through `arcp.middleware.asgi`), `aiohttp` server, and `otel`
>   propagation. Optional defensible adds: `litestar`, `quart`. Reject
>   abandoned hosts (`tornado` unless argued).
> - For each: how WS upgrade attaches (ASGI lifespan + websocket scope,
>   aiohttp `WebSocketResponse`), DNS-rebind / Host-header protection seam,
>   one-line API sketch.
> - The `otel` adapter parity with `@arcp/middleware-otel` — W3C
>   traceparent header on connect, span per envelope, attribute names
>   matching the TS adapter so traces cross SDKs cleanly.
> - Reject anything that would be slop: a generic "Django middleware" if
>   nobody runs ARCP servers under Django; a `flask` adapter if Flask
>   can't do native WS without `flask-sock`.

### Phase 6 — Examples (subagent)

> You are mapping the 18 TS examples to Python. Read
> `../typescript-sdk/examples/README.md`, then 01 + 02 + 04. Produce
> `planning/v1.1/06-examples.md`:
>
> - One row per TS example: TS name → Python example name (kebab- or
>   snake-case, pick), files (`server.py`, `client.py`), one-sentence
>   description anchored to the spec §, and the Python idiom it shows
>   off (e.g. `result-chunk/` uses `async for chunk in result.chunks()`,
>   not callback registration).
> - Each example must run with one command (`python -m arcp.examples.<name>`
>   or a `runner.py`); the runner exits 0 on success.
> - State a common shape (CLI args, env vars, transport pairing) so a
>   reader can spot-check by skimming any single example.

### Phase 7 — Tests (subagent)

> You are designing the test plan. Coverage floor: 87% lines AND
> branches. Read 01 + 02 + 04 + 06. Produce `planning/v1.1/07-tests.md`:
>
> - Stack: `pytest` + `pytest-asyncio` (or `anyio`) + `hypothesis` +
>   `pytest-cov`. Justify any addition (`pytest-randomly`, `freezegun`,
>   `dirty-equals`).
> - Layered plan: envelope unit → message unit → session/job state
>   machine → end-to-end with real `MemoryTransport` and `WebSocketTransport`
>   (loopback) → conformance harness keyed to `CONFORMANCE.md` rows.
> - Property tests: where they pay rent (envelope round-trip, monotonic
>   `event_seq`, idempotency-key dedupe, lease subset check). Where they
>   don't.
> - Cancellation/timeout patterns under `asyncio`: explicit
>   `pytest.raises(asyncio.CancelledError)` shape, no `asyncio.sleep`
>   races, no `pytest.warns` for the cancellation path.
> - CI matrix: defensible Python versions (e.g. 3.11, 3.12, 3.13). State
>   why each.
> - "Minimum to hit 87%": which modules will be cheap, which expensive,
>   and which (if any) get a documented carve-out (e.g. `__main__`).

### Phase 8 — Docs & README (subagent)

> You are planning the docs. Shared docs site ingests plain Markdown
> from each SDK's `docs/` directory; do **not** introduce a per-SDK doc
> generator. Read 01 + 02 + 04 + 06. Produce
> `planning/v1.1/08-docs-readme.md`:
>
> - Docs tree under `docs/`: `00-overview.md`, `01-quickstart.md`,
>   `02-concepts.md`, `03-features/*.md` (one per v1.1 feature),
>   `04-examples/*.md` (one per example), `05-reference/*.md` keyed to
>   public API from Phase 4, `06-conformance.md`.
> - Frontmatter schema: `title`, `sdk: python`, `spec_sections: []`,
>   `order`, `kind ∈ {overview, guide, feature, example, reference,
>   conformance}`. Identical across SDKs — that's what lets the shared
>   site style them uniformly.
> - README outline tailored to Python: `uv add arcp` (and `pip install`
>   for completeness), quickstart that compiles and exits 0, packaging
>   table mirroring the TS one (`arcp` umbrella, `arcp.client`,
>   `arcp.runtime`, `arcp.middleware.asgi`, etc.).
> - Voice: terse, no marketing tone, no emojis, no second-person
>   exhortations ("simply", "just"). Code blocks must be runnable.

### Phase 9 — Diagrams (subagent)

> You are planning the Graphviz diagrams shipped under `docs/diagrams/*.dot`.
> Read 01 + 04 + 06. Produce `planning/v1.1/09-diagrams.md`:
>
> - Minimum set: (a) module dependency graph, (b) session lifecycle
>   state machine, (c) job lifecycle with v1.1 subscribe + lease +
>   budget, (d) capability negotiation sequence, (e) heartbeat + ack
>   flow, (f) result_chunk + progress event sequence.
> - For each: filename, render command (`dot -Tsvg`), node/edge style
>   conventions (so all SDK diagrams look like siblings on the docs
>   site), and the docs page that embeds it.
> - No diagram that isn't load-bearing for understanding.

### Phase 10 — Synthesis (you)

After all subagents return, read every plan. Produce
`planning/v1.1/10-synthesis.md`:

- One-page executive summary: scope, library picks, test floor, doc
  target.
- Cross-phase contradictions or seams discovered; how they're resolved.
- Ordered milestones, each scoped so it could ship as one PR — list the
  files added/modified and the spec § it lands.
- Risks + explicit non-goals.
- Open questions for the human reviewer.

## Anti-slop guardrails (apply to every phase)

Reject and rewrite any of these:

- Words: "leverage", "robust", "scalable", "performant", "powerful",
  "modern", "easy to use", "developer-friendly", "best-in-class".
- Bullets that restate their heading.
- Tables or trees that could be produced for any SDK without edits.
- Paragraphs that don't reference at least one of: spec §, TS path, this
  SDK's path, a named library, a Python-specific idiom.
- A "Future work" section that's not a real list of concrete items.
- Generic risk lists ("performance", "compatibility"). Risks must name
  a concrete thing (e.g. "msgspec strictness may reject `unknown`
  top-level fields the spec says to ignore — verify before commit").

## What good looks like

Each plan file is short enough that a senior reviewer reads it in
under 8 minutes, dense enough that every paragraph rules something in
or out, and specific to Python + ARCP v1.1 — never recyclable as a
generic AI-SDK template.

---

## Python candidate shortlist (Phase 3 seed)

Concrete starting points. Phase 3 picks one per row, with a one-liner
justifying the rejection of the others.

| Concern             | Candidates                                                              |
| ------------------- | ----------------------------------------------------------------------- |
| Schema/validation   | `pydantic` v2, `msgspec`, `attrs`+`cattrs`                              |
| WebSocket           | `websockets`, `aiohttp`, `httpx-ws`                                     |
| HTTP                | `httpx`, `aiohttp`                                                      |
| Async runtime       | stdlib `asyncio`, `anyio`                                               |
| Logging             | stdlib `logging` + `structlog`                                          |
| ULID / UUIDv7       | `python-ulid`, `uuid-utils`, `uuid7`                                    |
| Tracing             | `opentelemetry-api` (runtime: `opentelemetry-sdk`)                      |
| Testing             | `pytest`, `pytest-asyncio` or `anyio`, `hypothesis`, `pytest-cov`       |
| Typecheck           | `mypy --strict`, `pyright --strict`                                     |
| Lint/format         | `ruff` (lint + format)                                                  |
| Build               | `uv`, `hatchling` (PEP 621)                                             |
| ASGI middleware     | native ASGI (works under Starlette/FastAPI/Litestar)                    |
| aiohttp middleware  | `aiohttp.web` `WebSocketResponse`                                       |
