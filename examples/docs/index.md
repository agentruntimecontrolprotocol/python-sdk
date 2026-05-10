# ARCP Python Examples — Documentation

Eleven applications, one protocol. Read this first; pick an example; run it.

## Concepts

Cross-cutting design notes that the examples share:

- [Providers](concepts/providers.md) — how the LLM abstraction works and how `ScriptedProvider` makes every test deterministic.
- [Destinations](concepts/destinations.md) — the human-in-the-loop fan-out / race / cancel model.
- [Auth](concepts/auth.md) — bearer, JWT, LDAP fixtures and how they switch to real mode.
- [Observability](concepts/observability.md) — recording sinks vs real Langfuse / Datadog / OTel.
- [Testing](concepts/testing.md) — in-memory transport pairing, parametrized end-to-end tests, real-mode gating.

## Examples by RFC section

| RFC section | Example(s) |
|---|---|
| §6.5 priority | 3, 11 |
| §7 capability negotiation | 4 (extension), all (handshake) |
| §8 auth | 6 (LDAP+JWT), 5 (JWT+identity), 3 |
| §10.3 heartbeats | 10 |
| §11 streams | 1 (text), 11 (thought) |
| §11.2 backpressure | 11 |
| §11.4 thought streams | 11, 7 |
| §12.2 choice request | 3 |
| §13 subscriptions | 7, 11 (observer) |
| §14 delegate | 2, 8 |
| §14 handoff | 5 |
| §15 permissions | 1, 6 |
| §15.5 leases | 1, 6 |
| §15.6 trust elevation | 6 |
| §16 artifacts | 10 |
| §17 observability | 7, 8 |
| §17.3 standard metrics | 2, 5, 7, 9 |
| §18 retryable errors | 9 |
| §19 resume | 10, 8 |
| §21 extensions | 4 |

## What you'll learn

- How the §6.1 envelope carries every wire message and what each field does in practice.
- How to set up a runtime that advertises capabilities, accepts authenticated sessions, and dispatches commands.
- How to handle streams with backpressure without dropping payload-critical chunks.
- How human input fans out to multiple destinations and resolves to the first valid response.
- How permissions, leases, and trust elevation compose to gate sensitive operations.
- How to make a job durable (heartbeats, checkpoints, resume) and recover transparently from disconnects.
- How to instrument the runtime so the canonical observability tools just work.
- How to add domain-specific message types without breaking core conformance.
