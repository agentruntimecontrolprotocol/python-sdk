# `arcp` Python SDK — Refactor Plan

This document is the running log of the modernize-to-idiomatic-Python refactor
applied to `python-sdk/`. It is the source of truth for what this refactor
does, what it explicitly does not do, and the judgment calls made along the
way. Update it as phases land; if a future maintainer asks "why is this code
like this?" the answer should be either in the diff or in this plan.

---

## Baseline (captured 2026-05-10)

| Metric | Value |
| --- | --- |
| Python venv | 3.14.2 (project `.venv`, fresh) |
| Tests | **159 passed**, 0 failed, 0 skipped |
| Runtime | ~3.3 s wall (`uv run pytest`) |
| Coverage | **86%** (statements + branch, `arcp` package) |
| `ruff format --check .` | 26 files would be reformatted |
| `ruff check` (current narrow rule set: `E,F,W,I,B,UP,N,RUF`) | clean |
| `ruff check` (prompt-recommended broad rule set, no `D`) | 105 findings |
| `ruff check` (prompt-recommended broad rule set + `D`) | 385 findings |
| `pyright` (strict on `src/arcp`, relaxed `Unknown*`) | 0 errors, 0 warnings |
| `uv build` | wheel + sdist succeed, no warnings |

Output saved to `baseline.txt` (test run) and `phase0-issues.txt` (broad ruff
report). Gate 0 is captured at this point.

---

## Inventory

### Package shape

- Single distribution `arcp` (PyPI name) at `src/arcp/` — already on `src` layout.
- Build backend: `hatchling` via `pyproject.toml`. No `setup.py`/`setup.cfg`
  remain; nothing to migrate in Phase 2.
- Console script: `arcp = arcp.cli:main` via `[project.scripts]`. Working.
- Public modules (38 source files):
  - `arcp.envelope`, `arcp.errors`, `arcp.extensions`, `arcp.version`, `arcp.cli`
  - `arcp.messages.*` — pydantic payload models (10 modules)
  - `arcp.transport.*` — `base`, `in_memory`, `stdio`, `websocket`
  - `arcp.auth.*` — `bearer`, `jwt`
  - `arcp.runtime.*` — `server`, `session`, `job`, `stream`, `subscription`,
    `lease`, `pending`, `artifact`
  - `arcp.client.client`, `arcp.client.handlers`
  - `arcp.store.eventlog`
- Tests (26 files): `tests/unit`, `tests/integration`, `tests/e2e`. All
  pytest-style. No `unittest.TestCase`.
- Examples (7 files): `examples/01_minimal_session.py` … `06_relay_human_in_the_loop.py`
  plus `_common.py`. Numbered to match the protocol concept they
  demonstrate; align with samples in the other-language SDKs (csharp/go/rust/etc).

### Dependency landscape

Production: `pydantic>=2.7,<3`, `aiosqlite>=0.20`, `websockets>=13`,
`structlog>=24`, `pyjwt[crypto]>=2.9`, `click>=8.1`, `jsonschema>=4.23`. All
current; none abandoned.

Dev (currently `[project.optional-dependencies]`, will move to
`[dependency-groups]` in Phase 2): `pytest>=8`, `pytest-asyncio>=0.24`,
`pytest-cov>=5`, `ruff>=0.6`, `pyright>=1.1`. Phase 0 also adds
`pre-commit>=3` and (Phase 8) `hypothesis>=6`.

`uv.lock` exists; was originally generated against a now-deleted
`arcp-sdk/` subdirectory and so encoded a stale package path. Fixed by
running `uv sync` from the real project root and rebuilding the venv.

### Type hint coverage

Already very high — `from __future__ import annotations` is in every
substantive module; `X | None`, `dict[str, K]`, `Self`, etc. are already
used. `pyright --strict` already passes on `src/arcp` with four narrow
relaxations (`reportUnknownMemberType`, `reportUnknownVariableType`,
`reportUnknownArgumentType`, `reportUnknownParameterType` set to `false`).
These are the only suppressions and are the principal target for Phase 5.

### Async surface

The runtime is end-to-end `asyncio`. No threads. No `multiprocessing`.
Patterns to modernize in Phase 7:

- 3 call sites of `asyncio.wait_for(...)` — convert to `async with
  asyncio.timeout(...)` (3.11+).
- No `asyncio.gather` for fan-out (already uses `TaskGroup` in `runtime/server.py`
  and `runtime/job.py`). Verify in Phase 7.
- No `asyncio.run()` in library code. CLI entry point only.
- 7 ruff `ASYNC109` findings flag `async def f(..., timeout: float)` — these
  are deliberate public-API timeouts that callers pass through to internal
  `asyncio.timeout(...)` blocks; document the rationale and `# noqa: ASYNC109`
  with reason in Phase 7.

### Lint findings (broad rule set, excluding `D` pydocstyle)

| Code | Count | Phase | Notes |
| --- | --- | --- | --- |
| `ARG001` | 37 | Phases 4/5 | Most are pytest fixture arguments and protocol-conformance signatures; the rest are real cleanups. |
| `ARG002` | 2 | Phase 5 | Same. |
| `TRY003` | 27 | Phase 6 | "Avoid long messages outside the exception class" — addressed by enriching the `ARCPError` hierarchy and moving messages into typed fields. |
| `SIM105` | 17 | Phase 4 | `try/except/pass` → `contextlib.suppress(...)`. Mechanical. |
| `E501` | 11 | Phase 1 (incl. format pass) | Mostly inside long pydantic `Field(description="...")` strings; either accept (per-line `# noqa: E501` with reason) or wrap. |
| `ASYNC109` | 7 | Phase 7 | See above. |
| `SIM102` | 1 | Phase 4 | Single-occurrence collapsible-if. |
| `RET504` | 1 | Phase 4 | Unnecessary assign-then-return. |
| `TRY301` | 1 | Phase 6 | "Abstract `raise` to inner function" inside `runtime/server.py`. |
| `PT006` | 1 | Phase 8 | `parametrize` argument type. |

### Lint findings (`D` pydocstyle, deferred to Phase 9)

| Code | Count | Notes |
| --- | --- | --- |
| `D103` | 98 | Most are inside test files where docstrings are not required (tests are self-documenting via descriptive names). Will configure `D` to ignore tests. |
| `D202` | 62 | Blank-line-after-function. Auto-fixable in the format pass. |
| `D101` | 53 | Public class missing docstring — real work for Phase 9. |
| `D102` | 52 | Public method missing docstring — Phase 9. |
| `D107` | 8 | `__init__` missing docstring — Phase 9 or skip per Google style. |
| `D104` | 4 | Public package missing docstring — Phase 9 (4 `__init__.py` files). |
| `D105` | 3 | Magic-method docstrings — typically skip per Google style. |

---

## Per-phase plan

### Phase 0 — Survey, plan, baseline ✅

This document, `baseline.txt`, `phase0-issues.txt`. Tooling baseline (see
"Tooling configuration" below). Pre-commit config installed but not yet
gating. No source files changed.

### Phase 1 — Format and trivial autofixes

- `uv run ruff format .` — applies to 26 files; one commit.
- `uv run ruff check --fix --select I,UP,F,E,W .` — autofix import order,
  pyupgrade rewrites, pyflakes, pycodestyle. The current narrow rule set
  already covers all of these and passes, so the diff here is expected to
  be small (just whatever the format pass disturbs).
- Spot-check pyupgrade rewrites.
- Gate: tests still green; coverage ≥86%.

### Phase 2 — Project structure / packaging

- Already on src layout, hatchling, `pyproject.toml`. The packaging
  refactor for this project is narrow:
  - Move dev deps from `[project.optional-dependencies] dev` to
    `[dependency-groups] dev` (PEP 735).
  - Confirm `uv build` still produces an identical wheel.
  - Delete the stale `arcp-sdk/` untracked scratch dir; fix the README
    quickstart that references a non-existent path.
  - Confirm no transitively-unused imports via `ruff check --select F401`.
- Gate: `uv build` clean, tests green, coverage ≥86%.

### Phase 3 — Type hints, public API first

- Tighten `[tool.pyright]`: drop `reportUnknownMemberType`,
  `reportUnknownVariableType`, `reportUnknownArgumentType`,
  `reportUnknownParameterType` relaxations for public modules
  (`envelope`, `errors`, `extensions`, `messages.*`, `version`,
  `client.*`, `runtime.server`, `auth.*`, `transport.base`).
- Walk leaf-first; narrow remaining `Any` in public signatures (envelope
  `payload` is the principal trust boundary — keep `Any` there but document
  it).
- Add `typing.override` where overriding (3.12+).
- Gate: pyright clean across declared public modules; tests green.

### Phase 4 — Modernize syntax

- `SIM105`: `try/except/pass` → `contextlib.suppress(...)` (17 sites).
- `os.path` → `pathlib`: greppable check shows zero current sites; nothing
  to do beyond the eventlog SQLite path which already uses `Path`.
- Replace `asyncio.wait_for(...)` with `async with asyncio.timeout(...)`
  in `runtime/job.py:268`, `runtime/job.py:338`, `client/client.py:143`
  (3 sites). (This straddles Phase 4 and 7 — apply in 7 alongside other
  async modernization.)
- Spot-fix `SIM102`, `RET504`.
- Continue using f-strings and `match` where they already are; no large
  sweeps expected.
- Gate: ruff `UP, SIM, C4, PTH, RET` clean; tests green.

### Phase 5 — Idiomatic patterns

- Tighten pyright fully (drop `Unknown*` relaxations across the entire
  `src/` tree — i.e. internal modules too).
- Audit inheritance — likely no changes needed; runtime modules are
  composition already.
- Confirm no mutable default arguments (`B006`) — current ruff run shows
  none. Re-verify after broadening.
- Confirm no bare `except:` — current ruff shows none.
- Properties vs. getter/setter — none observed; the project already uses
  attribute access.
- Gate: pyright strict clean across `src/`; ruff `B006`, `E722`, `RUF012`,
  `SLF` clean; tests green.

### Phase 6 — Error handling

- ARCP already has a structured error hierarchy in `arcp/errors.py`
  (`ARCPError(Exception)` with `code: ErrorCode`, retryability, structured
  details). Most `TRY003` findings are minor: messages are slightly long
  inline; will move them into typed exception subclasses where it's a
  cleanup, accept-and-ignore where the message is genuinely descriptive
  (with per-line `# noqa: TRY003 — descriptive message ...`).
- Address `TRY301` in `runtime/server.py` by extracting the abstracted
  raise.
- Audit transport layer — current `try: ... except Exception: pass` are all
  shutdown paths and should become `contextlib.suppress(BaseException)`
  with an explanatory comment.
- Gate: ruff `TRY` clean (or per-line ignored with reason); tests green.

### Phase 7 — Async/concurrency

- 3× `asyncio.wait_for` → `asyncio.timeout` (3.11+) — see Phase 4 note.
- Re-audit `runtime/server.py` and `runtime/job.py` to confirm `TaskGroup`
  is the structured-concurrency primitive everywhere fan-out happens.
- Document and `# noqa: ASYNC109` the 7 deliberate public-API `timeout=`
  parameters; they are part of the protocol surface.
- Gate: ruff `ASYNC` clean; tests green.

### Phase 8 — Test modernization

- Tests already use pytest patterns. Two specific upgrades:
  - Replace `asyncio.wait_for` in `tests/integration/test_cancellation.py`
    with `asyncio.timeout`.
  - Fix the lone `PT006` finding (parametrize argument-name type).
  - Add tests to push coverage on the four light modules (per user's
    decision to target ≥90% by Phase 9):
    - `auth/jwt.py` 55% → ≥90%
    - `runtime/pending.py` 60% → ≥90%
    - `transport/stdio.py` 66% → ≥90%
    - `runtime/session.py` 72% → ≥90%
- Add `hypothesis` for envelope and error-code round-trip properties where
  it's genuinely interesting.
- Gate: pytest coverage ≥90% (overall); ruff `PT` clean.

### Phase 9 — Docs and polish

- Enable `D` (pydocstyle) under Google convention; ignore tests via
  `[tool.ruff.lint.per-file-ignores]`.
- Add docstrings to remaining public classes/methods.
- Update README quickstart to work on a fresh clone.
- Add CHANGELOG section "Unreleased — Idiomatic refactor".
- Add `[tool.ruff.lint.pydocstyle] convention = "google"`.
- Final pass with strictest ruff config.
- Tag `refactor/phase-9-final`.

---

## Tooling configuration applied in Phase 0

### `pyproject.toml`

- `requires-python = ">=3.13"` (raised from `>=3.12` per user decision; the
  refactor's idiomatic targets — `asyncio.timeout`, `StrEnum`, `override`,
  `batched` — are 3.11/3.12 features, so 3.13 is comfortably above the
  floor).
- `[tool.ruff] target-version = "py313"` (matched).
- `[tool.ruff.lint] select` widened to:
  `E, W, F, I, N, UP, B, C4, SIM, RUF, PTH, PT, RET, TRY, ASYNC, ERA, ARG,
  SLF, TID, PERF`. (`D` deferred to Phase 9.)
- Per-file ignores:
  - Examples: `D` family (when enabled in Phase 9) and `T201` (allow `print`).
  - Tests: `D` family and `B011`.
- `[tool.ruff.lint.pydocstyle] convention = "google"` (active in Phase 9).
- `[tool.ruff.format] quote-style = "double"`, `indent-style = "space"`.
- `[tool.pytest.ini_options]` adds `--strict-markers --strict-config` to
  `addopts` (the existing `-ra` is preserved).
- `[tool.pyright]` keeps current strictness for Phase 0; Phase 3/5 tighten.
- Coverage config in Phase 8: `[tool.coverage.report] fail_under = 90` and
  set `--cov-fail-under=90` in `addopts`.

### `.pre-commit-config.yaml`

Added in Phase 0; runs `ruff` (with `--fix`) and `ruff-format` on commit;
runs `pyright` and `pytest -q` on push. Not yet a hard gate (developers
must opt in via `pre-commit install` locally; CI is the canonical gate).

### Why the dependency floors stay where they are

- `pydantic>=2.7,<3`: project is locked to v2 semantics. v3 is months out
  and a separate concern.
- `websockets>=13`: 16.0 is current; floor stays at 13 to allow downstream
  compatibility.
- All other floors stay; bumping floors is out of scope per the prompt.

### Why Python 3.13 (not 3.12)

User chose the higher floor at Phase 0 kickoff. 3.13 is widely available
(released 2024-10), the project ships nothing breaking against 3.12 today,
and raising the floor avoids paying attention to back-compat for any 3.13+
syntax we end up reaching for (notably PEP 696 type-parameter defaults if
they appear in Phase 3/5 work). No CI matrix change needed because there
is no per-version CI matrix today.

---

## Open questions (resolved)

- ~~Branch strategy~~: commit directly on `main` (per user, 2026-05-10).
- ~~`arcp-sdk/` stray dir~~: delete in Phase 2; fix README quickstart.
- ~~Coverage floor~~: target ≥90% by Phase 9 (per user).
- ~~Python floor~~: raise to 3.13 (per user).

## Open questions (still open)

- The CLI module (`src/arcp/cli.py`) is excluded from coverage today via
  `[tool.coverage.run] omit`. If we add a CLI smoke test in Phase 8 we can
  remove the omit and let it count toward the 90% target naturally; flag
  if you'd prefer to leave it omitted.
- Public-API stability: is the `0.1.0` surface considered stable, or are
  signature tweaks acceptable in this refactor? The hard rule says no
  signature changes without sign-off; default is no changes.

## Future work (out of scope)

- Migrate websockets to its v14 connection-handler API (separate concern).
- Add a CI matrix testing 3.13 + 3.14.
- Replace `aiosqlite` with synchronous `sqlite3` + offload to executor —
  performance experiment, not idiomatic-modern concern.
- Public-facing docs site (Sphinx / mkdocs).
- A genuine integration test against an external WebSocket peer.

---

## Phase log

| Phase | Status | Tag | Notes |
| --- | --- | --- | --- |
| 0 | in progress | `refactor/phase-0-baseline` | Baseline + plan + tooling. |
| 1 | pending | — | Format and trivial autofixes. |
| 2 | pending | — | Packaging tweaks; delete `arcp-sdk/`; README. |
| 3 | pending | — | Pyright strict on public API. |
| 4 | pending | — | Modern syntax sweeps. |
| 5 | pending | — | Pyright strict everywhere; idiomatic patterns. |
| 6 | pending | — | Structured exceptions / `TRY` clean. |
| 7 | pending | — | `asyncio.timeout`, `TaskGroup` audit. |
| 8 | pending | — | Test modernization, coverage to ≥90%. |
| 9 | pending | `refactor/phase-9-final` | Docstrings, README, CHANGELOG. |
