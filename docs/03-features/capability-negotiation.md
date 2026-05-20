---
title: "Capability negotiation"
sdk: python
spec_sections: ["§6.2"]
order: 1
kind: feature
---

## What it is

Capability negotiation is the meta-mechanism that gates every other
v1.1 feature. The client lists its supported features in
`session.hello.payload.capabilities.features`; the runtime echoes its
own list in `session.welcome.payload.capabilities.features`; both
sides take the intersection, in the client's declared order, and
operate against that set for the lifetime of the session. Features
absent from the intersection MUST behave as if unsupported on both
sides.

## Feature flag

This is the negotiation mechanism itself — there is no flag. The
flag vocabulary is the V1.1 set: `heartbeat`, `ack`, `list_jobs`,
`subscribe`, `lease_expires_at`, `cost.budget`, `progress`,
`result_chunk`, `agent_versions` (`arcp/_version.py:L8`).

## Wire example

```json
{
  "arcp": "1.1",
  "id": "01J9SHY...",
  "type": "session.hello",
  "payload": {
    "client": {"name": "demo", "version": "1.0.0"},
    "auth": {"scheme": "bearer", "token": "..."},
    "capabilities": {
      "encodings": ["json"],
      "features": ["ack", "subscribe", "progress"]
    }
  }
}
```

The runtime replies with `session.welcome` carrying its own feature
list; the negotiated set is `client ∩ runtime`, in client order.

## Python API

```python
from arcp import V1_1_FEATURES, intersect_features
from arcp.client import ARCPClient

client = ARCPClient(client=..., token=..., features=V1_1_FEATURES)
await client.connect(transport)

client.has_feature("ack")          # bool
client.negotiated_features         # tuple[str, ...]
```

`features=` defaults to `V1_1_FEATURES` (the full set). Pass a custom
tuple to advertise a subset. On the runtime side, `SessionContext`
exposes the same `negotiated_features` / `has_feature(name)` surface
(`arcp/_runtime/session.py:L75`); `_require_feature` in the dispatcher
turns missing-feature submissions into `INVALID_REQUEST`
(`arcp/_runtime/server.py:L390`).

## Failure modes

- `INVALID_REQUEST` — feature-gated verb invoked without negotiation
  (`arcp.errors.InvalidRequestError`).

## See also

- All sibling pages in [`03-features/`](.) describe the individual
  flags negotiated through this mechanism.
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §6.2.
