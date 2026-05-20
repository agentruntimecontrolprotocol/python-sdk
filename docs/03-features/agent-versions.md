---
title: "Agent versions"
sdk: python
spec_sections: ["§7.5", "§13.7"]
order: 6
kind: feature
---

## What it is

Clients may submit jobs against a specific agent version using
`name@version` in `job.submit.payload.agent`. The runtime resolves
the named version from its registry; bare `name` resolves to the
default version set via `set_default_agent_version`. Mismatch is a
`session.error` (not `job.error`), since no job is allocated.

## Feature flag

`agent_versions`

## Wire example

```json
{
  "arcp": "1.1",
  "id": "01J9SJ3...",
  "type": "job.submit",
  "session_id": "sess_01J9SHX...",
  "payload": {
    "agent": "weekly-report@2026.05.0",
    "input": {"week": "2026-W19"},
    "lease_request": {"net.fetch": ["s3://example/**"]}
  }
}
```

## Python API

```python
from arcp.runtime import ARCPRuntime

runtime.register_agent_version("weekly-report", "2026.05.0", weekly_report_v2)
runtime.register_agent_version("weekly-report", "2026.04.1", weekly_report_v1)
runtime.set_default_agent_version("weekly-report", "2026.05.0")
```

Resolution: `ARCPRuntime._resolve_agent` at
`arcp/_runtime/server.py:L185`; ref parsing via
`arcp.parse_agent_ref` (`arcp/_messages/execution.py`).

## Failure modes

- `AGENT_VERSION_NOT_AVAILABLE` — version unknown for the named
  agent; surfaces as `session.error`
  (`arcp.errors.AgentVersionNotAvailableError`).
- `AGENT_NOT_AVAILABLE` — agent name unknown
  (`arcp.errors.AgentNotAvailableError`).
- `INVALID_REQUEST` — malformed `name@version` token.

## See also

- Example: [`../04-examples/agent-versions.md`](../04-examples/agent-versions.md).
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §7.5.
