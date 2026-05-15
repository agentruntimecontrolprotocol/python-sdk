# Changelog

All notable changes to this project will be documented in this file. The
format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Refactor: PYTHON_SDK_GUIDE.md conformance.** Non-breaking internal
  restructure to meet the guide's hard limits and lint rules. No public
  API symbols were removed or renamed.
  - Split oversized modules along responsibility lines:
    - `_runtime/server.py` (744 LOC) → `server.py` + `_handshake.py`
      + `_accept.py` + `_handlers.py` + `_handler_list_jobs.py`
      + `_job_runner.py`.
    - `_client/client.py` (479 LOC) → `client.py` + `dispatch.py`
      + `ops.py`.
    - `_messages/execution.py` (348 LOC) → `execution.py`
      + `event_bodies.py`.
    - `_runtime/job.py` (372 LOC) → `job.py` + `result_stream.py`.
  - All source modules are now ≤ 296 lines (guide §0).
- Reduced cyclomatic complexity on `_dispatch`, `_run_job`,
  `is_lease_subset`, and `otel._extract_attrs` to ≤ 8 via guard-clause
  extraction and dict-of-handlers dispatch (guide §14).

### Added

- Tighter lint rules in `pyproject.toml`:
  - `ruff.lint.select` now includes `C90` (mccabe), `PLR` (pylint refactor).
  - `ruff.lint.mccabe.max-complexity = 8`.
  - `ruff.lint.pylint.max-args = 5`.
- `[tool.mypy]` block with `strict = true`, `warn_unreachable = true`,
  `plugins = ["pydantic.mypy"]`.
- `--cov-fail-under` raised from 60 → 90 (current actual: 73%).
- `mypy>=2.1` added to the `dev` dependency group.

### Fixed

- `mypy --strict` now passes (14 → 0 errors). Fixes include:
  - JSON-frame parsers in transports/middleware now check the parsed
    value is a `dict` before returning, eliminating `no-any-return`.
  - `EventLog.read_since_seq` Protocol signature aligned with async-
    generator semantics (the implementations stay unchanged).
  - `Envelope` `_envelope` validators no longer carry an unused
    `# type: ignore[unreachable]`.
  - CLI imports `ARCPClient` and `StaticBearerVerifier` from their
    public submodules (`arcp.client`, `arcp.runtime`) rather than a
    non-existent top-level re-export.

### Judgment calls

- **PLR0913 noqa for keyword-only constructors with optional knobs.**
  `JWTVerifier.__init__`, `ARCPClient.__init__`, `ARCPRuntime.__init__`,
  `ARCPClient.submit`, and a small number of private helpers carry a
  documented `# noqa: PLR0913`. Every argument is already keyword-only
  with a default; grouping them in a config dataclass is a breaking
  signature change with no clarity gain.
- **Coverage gate not yet met.** The guide and CI target is
  `--cov-fail-under=90`; current actual is 73%. New tests for
  server/transport branches are deferred.

## [1.1.0] – 2026-01

- Initial v1.1 reference implementation.
