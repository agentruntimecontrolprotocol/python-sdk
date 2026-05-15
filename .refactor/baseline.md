# Refactor Baseline (pre-work)

Captured: 2026-05-14

## Tests

- 139 passed, 3 skipped, 0 failed
- Coverage: 73.27% (gate target: 90%)
- Skipped tests are intentional documented races (see `tests/state/`)

## Ruff

- `ruff check .` — **0 violations** (with current ruleset)
- `ruff format --check .` — **0 files would change**

## Mypy strict

- 14 errors across 8 files (after installing mypy)
- Categories:
  - 4× `no-any-return` at Pydantic `.model_dump()`/typed-dict boundaries
  - 2× missing `arcp.ARCPClient`/`StaticBearerVerifier` re-exports for CLI
  - 1× server `EventLog`/`InMemoryEventLog` Liskov mismatch
  - 1× server `_subscribe` missing `await` on async iter call
  - 1× client `Job*Payload` Liskov mismatch
  - 1× CLI `event_log` argument typing
  - misc unused-ignore / name-defined

## Hard-limit violations (Guide §0)

### Files > 300 lines
- `src/arcp/_runtime/server.py` — 744
- `src/arcp/_client/client.py` — 479
- `src/arcp/_runtime/job.py` — 372
- `src/arcp/_messages/execution.py` — 348

### Functions > 5 args / complexity > 8
- `src/arcp/_auth/jwt.py:16` — `JWTVerifier.__init__` (7 args)
- `src/arcp/_client/client.py:69` — `ARCPClient.__init__` (7 args)
- `src/arcp/_client/client.py:183` — `submit` (8 args)
- `src/arcp/_client/client.py:291` — `_handshake` (11 args)
- `src/arcp/_runtime/server.py:110` — `ARCPRuntime.__init__` (>5 args)
- `src/arcp/_runtime/server.py:340` — `_dispatch` (complexity 11)
- `src/arcp/_runtime/server.py:532` — `_run_job` (complexity 11)
- `src/arcp/_runtime/session.py:150` — `make_session_state` (6 args)

### Other inventory
- `__all__` missing: `cli.py`, `__main__.py` (both are CLI entry points — acceptable)
- `from __future__ import annotations` missing on a few `__init__.py` shims (acceptable; they have no annotations)
- `setup.py` / `setup.cfg`: none (PEP 621 already)
- `src/` layout: ✓ already
- `py.typed` marker: present
