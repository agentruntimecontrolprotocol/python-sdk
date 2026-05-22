# ARCP Python SDK

The **Agent Runtime Control Protocol (ARCP)** Python SDK implements [ARCP v1.1](https://arcp.dev/spec/v1.1) — a message protocol for autonomous agent job submission, streaming, observability, and lifecycle control.

## Install

```bash
pip install arcp
# or with uv:
uv add arcp
```

Requires Python 3.11+.

## Start here

| | |
|---|---|
| [Getting started](getting-started.md) | Five-minute end-to-end example |
| [Architecture](architecture.md) | How the SDK is structured and why |
| [Conformance](conformance.md) | Which spec sections are implemented |

## Guides

One guide per ARCP spec section:

| Guide | Spec |
|---|---|
| [Sessions](guides/sessions.md) | §6 — Session lifecycle |
| [Stream resume](guides/resume.md) | §6.3 — Resuming interrupted streams |
| [Authentication](guides/auth.md) | §6.1 — Bearer tokens and custom verifiers |
| [Jobs](guides/jobs.md) | §7 — Submitting and running jobs |
| [Job events](guides/job-events.md) | §8 — Event kinds and typed payloads |
| [Leases](guides/leases.md) | §9 — Cost and time budgets |
| [Delegation](guides/delegation.md) | §10 — Agent-to-agent trust chains |
| [Observability](guides/observability.md) | §11 — Logging, tracing, and metrics |
| [Errors](guides/errors.md) | §12 — Typed exceptions |
| [Vendor extensions](guides/vendor-extensions.md) | §15 — Custom `x-*` fields |

## Reference

| | |
|---|---|
| [Transports](transports.md) | In-memory, WebSocket, stdio |
| [CLI](cli.md) | `arcp serve`, `submit`, `tail`, `replay` |
| [Troubleshooting](troubleshooting.md) | Common errors and fixes |

## Recipes

See [recipes.md](recipes.md) for a full index of runnable examples.

## Links

- [ARCP Specification v1.1](https://arcp.dev/spec/v1.1)
- [TypeScript SDK](https://github.com/agentruntimecontrolprotocol/typescript-sdk)
- [PyPI: arcp](https://pypi.org/project/arcp/)
- [Changelog](../CHANGELOG.md)
