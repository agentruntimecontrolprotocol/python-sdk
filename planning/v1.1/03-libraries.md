# 03 — Library Picks

Scope: pin every runtime and tooling dependency the v1.1 SDK will use.
Inputs: spec [`draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md)
§4–§12; v1.0→v1.1 delta in [`01-spec-delta.md`](01-spec-delta.md); module
landing zones in [`02-current-audit.md`](02-current-audit.md) §2/§3.
Existing deps in [`../../pyproject.toml`](../../pyproject.toml) are the
baseline; every entry below either confirms or replaces a line there.

## Decisions at a glance

| Concern                  | Pick                                  | Lands in                                                                 |
| ------------------------ | ------------------------------------- | ------------------------------------------------------------------------ |
| Schema / validation      | `pydantic` v2 (≥ 2.9, < 3)            | `arcp/_envelope.py`, `arcp/_messages/*`                                  |
| WebSocket (client + svr) | `websockets` (≥ 13)                   | `arcp/transport/websocket.py`                                            |
| HTTP client              | `httpx` (≥ 0.27)                      | `arcp/auth/jwt.py` (JWKS fetch only)                                     |
| Async runtime            | stdlib `asyncio` only                 | every `arcp/_runtime/*`, `arcp/_client/client.py`                        |
| Logging                  | stdlib `logging` + `structlog` (≥ 24) | `arcp/_logging.py`, all callsites via `structlog.get_logger`             |
| ID generation            | `python-ulid` (≥ 2)                   | `arcp/_ids.py` (consumed by `_envelope`, `_runtime/job`, `_runtime/session`) |
| Tracing                  | `opentelemetry-api` (≥ 1.27), API-only | `arcp/middleware/otel/`                                                  |
| JWT verify               | `pyjwt[crypto]` (≥ 2.9)               | `arcp/auth/jwt.py`                                                       |
| Storage                  | `aiosqlite` (≥ 0.20)                  | `arcp/_store/eventlog.py`                                                |
| CLI                      | `click` (≥ 8.1)                       | `arcp/cli.py`                                                            |
| Test runner              | `pytest` + `pytest-asyncio` + `hypothesis` + `pytest-cov` | `tests/`                                              |
| Lint / format            | `ruff` (≥ 0.6)                        | repo-wide                                                                |
| Type checker             | `pyright --strict` (≥ 1.1)            | `src/arcp`, `tests/`                                                     |
| Build backend            | `hatchling` (PEP 621)                 | `pyproject.toml` `[build-system]`                                        |
| Package manager          | `uv` (≥ 0.4)                          | `uv.lock`                                                                |
| Minimum Python           | 3.11                                  | `requires-python = ">=3.11"`                                             |
| Drop `jsonschema`        | yes                                   | removed from `[project.dependencies]`                                    |
| Mutation testing         | no                                    | —                                                                        |

## 1. Schema / validation → `pydantic` v2

The SDK validates the v1.0 8-field envelope (§5.1) plus ~30 payload types
across `arcp/_messages/session.py` and `arcp/_messages/execution.py`
(see file map in [`02-current-audit.md`](02-current-audit.md) §2), and
must validate each `result_chunk` event body on the hot path (§8.4 +
[`01-spec-delta.md`](01-spec-delta.md) §1 row §8.4). Pick: `pydantic` v2
over `msgspec` and `attrs`+`cattrs`. The deciding factor is interop with
the choices below — `pydantic` is already used in `auth/jwt.py` config
shapes via downstream FastAPI integrations the audit assumes consumers
have, its `model_config(extra="ignore")` is the natural fit for the
"ignore unknown top-level envelope fields" rule that v1.0 §5.1 makes
mandatory (quoted in [`01-spec-delta.md`](01-spec-delta.md) §1), and its
discriminated-union support handles the `job.event.payload.kind` switch
(§8.2: `log`, `thought`, `tool_call`, `tool_result`, `status`, `metric`,
`artifact_ref`, `delegate`, `progress`, `result_chunk`) without manual
dispatch tables. License + signal: MIT, 2.9.2 released Sept 2024; weekly
patch cadence on `main`. Lands in `arcp/_envelope.py` and the entire
`arcp/_messages/*` tree.

Rejected: `msgspec` is roughly 5–20× faster on the small fast-path
`result_chunk` body, and Phase 2 risk §4 in
[`02-current-audit.md`](02-current-audit.md) flags this. The commitment
is still `pydantic` because the v1.1 hot-path workload is bounded: §14
caps `result_chunk` size at ~1 MB and the SDK is the validator on the
receive side, where decode dominates validation cost regardless of
library. Buying `msgspec` would force two parallel type models
(`msgspec.Struct` vs `pydantic.BaseModel`) — the audit's §4 explicitly
says "Phase 3 owns this; the v1.1 plan must commit to one." One model.
Rejected `attrs`+`cattrs` for the same reason plus weaker discriminated-
union ergonomics for the §8.2 `kind` union.

If `result_chunk` validation shows up in profiles after Phase 7 perf
tests, the escape hatch is a single `TypeAdapter` for the chunk body
with `validate_python(strict=False)` — measured swap, not a library
rewrite.

## 2. WebSocket → `websockets`

`websockets` covers both sides: client connect in
`arcp/transport/websocket.py` and server upgrade in the same module
(`websockets.serve` / `ServerProtocol`). The server-side WS upgrade
lives **inside the SDK**, not behind a user-provided ASGI app — this
matters for Phase 5 middleware (OTel + auth interceptors run on the
envelope stream, not HTTP). The current SDK already pins
`websockets>=13` and the audit marks `transport/websocket.py` as
"Salvage" ([`02-current-audit.md`](02-current-audit.md) §2). Confirm.
License + signal: BSD-3-Clause, 13.1 released Sept 2024; quarterly
minor releases, single-author project but in continuous use by every
async Python WS deployment. Backpressure measurement for §6.5
([`02-current-audit.md`](02-current-audit.md) §4 last bullet) uses
`websockets.WebSocketCommonProtocol.transport.get_write_buffer_size()`
on the asyncio implementation; this is the reason `websockets` wins
over `aiohttp` (which buries the buffer behind its own send queue and
makes the §6.5 backpressure `status` event hard to wire) and over
`httpx-ws` (client-only, no server primitive).

## 3. HTTP client → `httpx`

ARCP itself is WS. HTTP appears in exactly one place: JWKS fetch in
`arcp/auth/jwt.py` when a JWT verifier resolves a `kid` against a remote
JWKS URL. Pick `httpx` (async + sync from one client; the JWKS-refresh
caller can be sync at config time and async at verify time) over
`aiohttp` (async-only, drags a second event-loop integration the SDK
doesn't otherwise need) and stdlib `urllib.request` (sync-only, no
connection pooling — JWKS rotation under load thrashes it). The framing
"HTTP client: not needed — JWKS fetches happen in user code" is
**rejected**: the audit lists `auth/jwt.py` as "Salvage"
([`02-current-audit.md`](02-current-audit.md) §2), and the verifier
needs to refresh JWKS to honor `kid` rotation per the JWT spec; pushing
that into user code makes every consumer reimplement a cache. License +
signal: BSD-3-Clause, 0.27.2 released Aug 2024; monthly releases.
`httpx` becomes a **conditional** runtime dep — gated behind a
`pyproject.toml` `[project.optional-dependencies] jwks = ["httpx>=0.27"]`
extra so static-JWK and static-secret verifiers don't pay for it.

## 4. Async runtime → stdlib `asyncio` only

Reject `anyio` / trio interop. The audit's §4 calls out four
asyncio-specific seams: `TaskGroup` for structured concurrency,
`CancelledError` propagation into agent coroutines, atomic
`event_seq` bump inside one coroutine frame, and the heartbeat-loop
exclusion from the session's `TaskGroup`. Three of those four reason
about behavior `anyio` papers over: `anyio.CancelScope` semantics
differ subtly from `asyncio.CancelledError`, and `anyio`'s
backend-portability layer is the wrong place to specify exactly which
cancellation channel the lease-expiry watchdog uses
([`02-current-audit.md`](02-current-audit.md) §3 H/M risk rows; §4
first bullet). License + signal for the rejected `anyio`: MIT, 4.6.2
released Oct 2024 — fine library, wrong tool for an SDK that has to
pin cancellation semantics for its own correctness proofs. Stdlib
only. Minimum 3.11 (see §13 below) gives us `asyncio.TaskGroup`,
`asyncio.timeout`, and the exception-group machinery the
`HeartbeatLostError` design needs.

## 5. Logging → stdlib `logging` + `structlog`

`structlog>=24` is already in `pyproject.toml` and the audit treats
`arcp/_logging.py` as a new module (Phase 5 middleware home). Confirm.
The pattern is `structlog.configure(...)` with a stdlib `LoggerFactory`
so library consumers can route ARCP logs through their existing
`logging.config.dictConfig` without `structlog` becoming a transitive
configuration concern. License + signal: Apache-2.0 / MIT, 24.4.0
released Aug 2024; quarterly releases.

Reject `loguru` explicitly: it installs a global sink on import,
reconfigures stdlib `logging` by default, and a library that imports
`loguru` silently changes its consumer's logging tree. That is the
textbook "library should not configure logging" anti-pattern; the
project README of `loguru` itself acknowledges it is application-
oriented. Excluded.

## 6. IDs (ULID + UUIDv7) → `python-ulid`

v1.0 §5.1 requires envelope `id` to be ULID or UUIDv7; the spec
examples (`sess_01J...`, `job_01J...`, `res_01J...` in §6.2 / §8.4)
prefix-encode ULIDs. Pick `python-ulid` over `uuid-utils` and
`uuid7`. Decider: `python-ulid` is pure-Python (no `cffi`/`maturin`
wheel matrix to ship across our 3.11/3.12/3.13 + macOS/Linux/Windows
support grid), and the `prefix-base32` form the spec uses is its
native output. UUIDv7 isn't needed alongside — pick one ID scheme for
the SDK and stick to it. `uuid-utils` is Rust-backed and produces both
but adds a wheel build matrix for one function call. License +
signal: MIT, 2.7.0 released Aug 2024; biannual releases, stable API.
Lands in a new `arcp/_ids.py` consumed by `arcp/_envelope.py` (envelope
`id`), `arcp/_runtime/session.py` (session_id), `arcp/_runtime/job.py`
(job_id), and result-stream `result_id` (§8.4).

## 7. Tracing → `opentelemetry-api` (API-only)

Confirm `opentelemetry-api` (not `-sdk`) as a runtime dep. The library
emits spans using `trace.get_tracer(...)` and span attributes
`arcp.lease.expires_at` / `arcp.budget.remaining` (spec §11;
[`01-spec-delta.md`](01-spec-delta.md) §1 row §11) but **does not
configure** a tracer provider. Consumers pull in `opentelemetry-sdk`
and exporters; if they don't, the API's `NoOpTracerProvider` makes the
SDK's instrumentation a no-op. License + signal: Apache-2.0, 1.27.0
released Sept 2024; six-week release cadence, OpenTelemetry-governance
stable API. Lands in `arcp/middleware/otel/` (new tree, see Phase 5).
Pin: `opentelemetry-api>=1.27,<2`.

## 8. JWT verification → `pyjwt[crypto]`

Confirm. Already used in `arcp/auth/jwt.py` which is salvaged
([`02-current-audit.md`](02-current-audit.md) §2). The `[crypto]` extra
pulls `cryptography` for RS256/ES256 verification — required for any
runtime accepting JWTs from an external IdP. License + signal:
MIT, 2.9.0 released July 2024; semiannual releases. No swap.

## 9. Storage → `aiosqlite`

Confirm. The audit marks `_store/eventlog.py` as Salvage (schema
rewrite for `event_seq` column) and `aiosqlite` is the only durability
dep in the tree. SQLite is the right choice for an SDK reference
implementation — file-backed, no server, supports the
[`01-spec-delta.md`](01-spec-delta.md) §1 row §6.5 ack-aware GC via a
single integer column index. License + signal: MIT, 0.20.0 released
May 2024; quarterly releases. Reject swapping to `asyncpg` or
`databases`: a Postgres dep would make `pip install arcp` require a
server. Reject pure stdlib `sqlite3` in a thread executor: the
audit's §4 risks already include "no await between seq bump and
emit", and putting blocking SQLite calls behind `run_in_executor`
creates exactly the interleaving hazard called out there.

## 10. CLI → `click`

Confirm. The audit lists `arcp/cli.py` as Rewrite (the verbs change)
but the framework is fine. Click ≥ 8.1 supports the subcommand groups
(`arcp serve`, `arcp send`, `arcp tail`, `arcp replay`) mirroring the
TS `pnpm tsx packages/sdk/src/cli.ts` surface. License + signal:
BSD-3-Clause, 8.1.7 released Aug 2023, 8.2 in late-2024 release
candidate. Reject `typer` (`click` wrapper, would add a dep for type-
hint sugar we don't need under `pyright --strict`) and `argparse`
(verb dispatch ergonomics worse than `click`'s `@group`).

## 11. Testing

- `pytest>=8` — confirm. The runner.
- `pytest-asyncio>=0.24` — confirm. With `asyncio_mode = "auto"`
  (already set in [`pyproject.toml`](../../pyproject.toml) §
  `[tool.pytest.ini_options]`). Since the runtime decision (§4 above)
  rejects `anyio`, do **not** add `pytest-anyio` or `anyio`'s pytest
  plugin.
- `hypothesis>=6.112` — **add**. The envelope (§5.1), `event_seq`
  monotonicity (§8.3), lease subsetting ([`02-current-audit.md`](02-current-audit.md)
  §3 H-risk row `validateLeaseSubset`), and the `cost.budget` amount
  grammar (§9.6 `currency:decimal`) are all property-test shaped.
  Hypothesis's `@given` over Pydantic models via `from_type` strategies
  is exactly the integration the type model in Phase 4 will want.
  License: MPL-2.0, weekly releases.
- `pytest-cov>=5` — confirm. The current `--cov-fail-under=90` floor
  ([`pyproject.toml`](../../pyproject.toml#L114)) stays.
- Mutation testing — **no**. `mutmut` and `cosmic-ray` mutate a tree
  exhaustively, take hours to converge, and for an SDK the ROI is bad:
  the wire is the spec, and conformance tests (Phase 7) catch
  mutations that matter. Reconsider once Phase 7 reports a coverage
  number above 95% with a stable test suite — not before.

## 12. Lint / format / static analysis

- `ruff>=0.6` — confirm. Already configured with a rule set
  ([`pyproject.toml`](../../pyproject.toml) `[tool.ruff.lint]`) that
  covers what `black` + `isort` + `flake8` + `pydocstyle` did. No
  change; `ruff format` is the formatter (no `black`).
- Type checker: **keep `pyright --strict`**, do not flip to
  `mypy --strict`. `pyright` is already configured strict for
  `src/arcp` ([`pyproject.toml`](../../pyproject.toml#L39)). Decider:
  `pyright` handles Pydantic v2's `BaseModel` generic protocol and
  discriminated unions (§8.2 `kind`) without a plugin; `mypy` needs
  `pydantic.mypy` and still trails on `Annotated`/`Discriminator`
  inference. License: Apache-2.0, weekly releases on `main`.

## 13. Build / packaging — `uv` + `hatchling`

Confirm. `[build-system] requires = ["hatchling"]` already pinned in
[`pyproject.toml`](../../pyproject.toml#L32). `uv` for the lockfile
([`uv.lock`](../../uv.lock) exists). Reject `poetry` (own resolver,
own lockfile format, slow), `setuptools` (no PEP 621 native parse
without extra config), `flit` (works fine, but `hatchling`'s build
hooks are a better fit for the per-Python-version wheel matrix we'll
need once `result_chunk` perf tests land in CI). License signal for
both: MIT (`hatchling` 1.25.0, `uv` 0.4.x), monthly releases.

## 14. Minimum Python — 3.11

Pin `requires-python = ">=3.11"`. Reject 3.10 (no `asyncio.TaskGroup`
without backport; structured concurrency is load-bearing for the
heartbeat / lease-expiry / subscriber fan-out coordination called out
in [`02-current-audit.md`](02-current-audit.md) §4). Reject 3.12 / 3.13
(today's `>=3.13` in
[`pyproject.toml`](../../pyproject.toml#L6) is too restrictive — major
distros ship 3.11 as default Python on 2024-LTS releases, and an SDK
that excludes them excludes its own consumers). 3.11 specifically
buys: `asyncio.TaskGroup`, `asyncio.timeout`, `ExceptionGroup` (the
heartbeat-loop sibling-cancellation pattern in §4 of the audit
depends on it), and `Self` / `LiteralString` typing primitives. 3.10
is not enough; 3.12 is more than we need.

## 15. Drop `jsonschema` — yes

Remove from `[project.dependencies]`. With Pydantic as the validator,
`jsonschema` is dead code — the audit's `pyproject.toml` flag
([`02-current-audit.md`](02-current-audit.md) §2 last list) says so
directly. If a consumer asks for a published JSON Schema document of
the v1.1 wire (Phase 8 docs may), Pydantic's
`TypeAdapter(...).json_schema()` produces it on demand. No runtime
need; no test need.

## 16. Summary diff vs current `pyproject.toml`

Runtime adds: `python-ulid>=2`, `opentelemetry-api>=1.27,<2`. Runtime
removes: `jsonschema>=4.23`. Runtime conditional: move `httpx>=0.27`
under `[project.optional-dependencies] jwks`. Dev adds: `hypothesis>=6.112`.
`requires-python` changes `>=3.13` → `>=3.11`; mirror in
`[tool.ruff] target-version = "py311"` and
`[tool.pyright] pythonVersion = "3.11"`. Everything else in the
existing manifest is confirmed.
