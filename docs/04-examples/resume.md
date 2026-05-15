---
title: "Session resume"
sdk: python
order: 3
kind: example
---

The client connects, submits a job, drops the transport mid-stream,
opens a new transport, and resumes the session with
`session.hello.payload.resume`. The runtime replays missed events
since `last_event_seq` from its event log.

Source: [`../../examples/resume/`](../../examples/resume/).

```sh
uv run python -m examples.resume.runtime &
uv run python -m examples.resume.client
```

## See also

- Reference: [`../05-reference/arcp-client.md`](../05-reference/arcp-client.md).
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §6.3.
