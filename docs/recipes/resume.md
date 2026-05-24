# Stream resume

The client connects, submits a job, drops the transport mid-stream,
opens a new transport, and resumes the session with
`resume_token` and `resume_from_seq`. The runtime replays missed events
since `last_event_seq` from its event log.

Source: [`../../examples/resume/`](../../examples/resume/).

```sh
uv run python -m examples.resume.server &
uv run python -m examples.resume.client
```

## See also

- Guide: [Stream resume](../guides/resume.md).
- Spec: [ARCP v1.1 §6.3](https://arcp.dev/spec/v1.1#section-6.3).
