# ARCP Python Examples

Reference implementations for the [Agent Runtime Control Protocol](../RFC-0001-v2.md). Eleven self-contained applications, one protocol surface each — runnable offline against scripted fixtures, runnable against real services when API keys are present.

## Quickstart

```bash
# From the python-sdk/ directory (or repository root with this path):
pip install -e .                                 # install the SDK
pip install -r examples/requirements.txt         # install example deps
python examples/01_sysops/main.py                # the simplest example
```

Every example accepts `--provider scripted` (default, no API keys needed). Pass `--provider <vendor>:<model>` and set the corresponding `ARCP_EXAMPLES_<VENDOR>_API_KEY` to run against a real LLM.

## The eleven examples

| # | Name | Demonstrates | LLM | Transport | Auth |
|---|---|---|---|---|---|
| [01](01_sysops/) | Sysops Agent | streams, permissions, leases | Anthropic | stdio | none |
| [02](02_subagents/) | Multi-Agent Research Squad | delegate, subscriptions, cost rollup | mixed | WebSocket | bearer |
| [03](03_code_review_veto/) | Code-Review Veto | choice request, fan-out HITL, priority | Anthropic | WebSocket | signed_jwt |
| [04](04_sdr_extension/) | SDR Control Plane | extensions, capability negotiation | GLM-4 | stdio | bearer |
| [05](05_tiered_handoff/) | Tiered Support Handoff | handoff, runtime identity, cost | Gemini → Anthropic | WebSocket | signed_jwt |
| [06](06_db_admin_permissions/) | DB Admin Permissions | LDAP auth, lease lifecycle, trust elevation | OpenAI | WebSocket | signed_jwt + LDAP |
| [07](07_triple_sink_observability/) | Triple-Sink Observability | subscriptions, standard metrics | mixed | WebSocket | bearer |
| [08](08_openclaw_orchestrator/) | OpenClaw Skill Orchestrator | delegate, resume, observability | Anthropic | WebSocket | signed_jwt |
| [09](09_litellm_marketplace/) | LiteLLM Marketplace | standard metrics, retryable errors | LiteLLM | WebSocket | bearer |
| [10](10_durable_research/) | Durable Research Pipeline | resume, artifacts, heartbeats | Anthropic | WebSocket | bearer |
| [11](11_reasoning_mirror/) | Reasoning Stream Mirror | thought streams, backpressure | OpenAI / DeepSeek | stdio + WebSocket | none |

## Layout

- `_shared/` — provider abstraction, destination relay, auth fixtures, observability sinks, OpenClaw stand-in, transport pairing helper.
- `NN_name/` — each example is a directory with `main.py`, `runtime.py`, `agent.py`, `fixtures/`, `tests/`, and a `README.md` that follows a strict template.
- `docs/` — cross-cutting concept docs (providers, destinations, auth, observability, testing).
- `EXAMPLES_PLAN.md` — running design log.

See [`docs/index.md`](docs/index.md) for a guided tour.

## Conventions

- Python 3.13, pyright strict, ruff for style. The configuration in [`.ruff.toml`](.ruff.toml) mirrors the SDK's.
- Every interesting line cites the RFC section it implements, e.g. `# §15.4: emit permission.request and block until grant`.
- Real-mode tests are guarded by `pytest.mark.skipif(os.getenv(...) is None)`; they skip cleanly when the gating env var is absent.
- No `print()` outside `main.py` entrypoints; structured logging via `structlog`.

## Running the tests

```bash
pytest examples/ -q
```

From the repository root. Default-mode coverage floor is 85% on the union of `_shared/` and each `NN_name/`.

## Why these eleven?

The protocol is small but the surface is broad. Eleven examples lets each pin a distinct primary feature without overlap, while letting incidental cross-feature usage (every example touches §6 envelopes, most touch §10 jobs, several touch §13 subscriptions) build familiarity gradually. The order is rough: simplest first, most service-integrated last.
