# Changelog

All notable changes to `arcp` are documented here. The format roughly follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Changed

- **Idiomatic-modern Python refactor** — non-functional. Coverage rose from
  86% to 90.22%; test count from 159 to 194. No public API changes; behavior
  is identical end-to-end. Details in `REFACTOR_PLAN.md`. Highlights:
  - Python floor raised from 3.12 to 3.13.
  - Pyright is now strict-clean across `src/arcp` without the four
    `reportUnknown*` relaxations the original config carried.
  - Ruff lint rule set widened to the prompt-recommended set
    (`E,W,F,I,N,UP,B,C4,SIM,RUF,PTH,PT,RET,TRY,ASYNC,ERA,ARG,SLF,TID,PERF,D`)
    and is fully clean. Narrow ignores documented inline.
  - `asyncio.wait_for` replaced with `async with asyncio.timeout(...)` at
    the three call sites that used it.
  - `@override` (PEP 698) added to overriding methods on Transport
    subclasses and `StaticTokenValidator.validate`.
  - 35 new unit tests for `auth.jwt`, `runtime.pending`,
    `runtime.session` (handshake), and `transport.stdio`.
  - Dev dependencies moved to PEP 735 `[dependency-groups]`. Added
    `pre-commit` to the dev group; `.pre-commit-config.yaml` runs
    ruff/pyright/pytest locally.
  - `--cov=arcp --cov-fail-under=90` is now wired into pytest `addopts`.
  - Public docstrings added on all reachable classes and methods; tests and
    examples are exempt from `D` per project convention.

## 0.1.0 — initial reference implementation

The original phase 0 → phase 7 implementation series. See `PLAN.md` and the
git history (`phase 0` through `phase 7` commits) for the per-phase
breakdown.
