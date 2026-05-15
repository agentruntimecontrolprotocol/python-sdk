---
title: "Overview"
sdk: python
order: 0
kind: overview
---

ARCP — the Agent Runtime Control Protocol — is a message protocol for
submitting jobs to autonomous agents and observing their execution. A
single bidirectional transport carries typed envelopes between a client
(the side submitting work) and a runtime (the side that hosts agents
and emits events). The protocol covers session handshake, job
lifecycle, structured event streams, lease-based authorization, and
delegation across runtimes.

This package, `arcp`, is the Python reference implementation of
ARCP v1.1. It ships:

- `arcp.client.ARCPClient` — async submit / subscribe / cancel / list.
- `arcp.runtime.ARCPRuntime` — accept loop, agent registry, lease
  enforcement, event log.
- Three transports: in-memory, WebSocket, stdio.
- ASGI, aiohttp, and OpenTelemetry middleware.
- A CLI (`arcp serve | submit | tail | replay`) for local exercise.

The wire is normative; this implementation tracks the published
protocol spec at
[`../../spec/docs/draft-arcp-02.1.md`](../../spec/docs/draft-arcp-02.1.md).
The conformance matrix in [`06-conformance.md`](06-conformance.md)
maps every spec section to a source citation.

## Where to start

- [`01-quickstart.md`](01-quickstart.md) — paired in-memory client and
  runtime in roughly 30 lines.
- [`02-concepts.md`](02-concepts.md) — envelopes, sessions, jobs,
  events, leases, delegation.
- [`03-features/`](03-features/) — one page per v1.1 negotiated
  feature.
- [`05-reference/`](05-reference/) — public API per module.
- [`06-conformance.md`](06-conformance.md) — spec-section status.

## Related

- TypeScript reference SDK:
  [`../../typescript-sdk/README.md`](../../typescript-sdk/README.md).
- Spec: [`../../spec/docs/draft-arcp-02.1.md`](../../spec/docs/draft-arcp-02.1.md).
- Examples: [`../examples/`](../examples/).
