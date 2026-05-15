---
title: "Agent versions"
sdk: python
order: 14
kind: example
---

The runtime registers two versions of `weekly-report`; the client
submits one job against `weekly-report@2026.05.0` and a second
against bare `weekly-report` (resolved to the default version), and
the example asserts both jobs ran the expected handler.

Source: [`../../examples/agent_versions/`](../../examples/agent_versions/).

```sh
uv run python -m examples.agent_versions.runtime &
uv run python -m examples.agent_versions.client
```

## See also

- Feature: [`../03-features/agent-versions.md`](../03-features/agent-versions.md).
