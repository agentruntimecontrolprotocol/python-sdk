# delegation

Research orchestrator that fans a single request out to three peer
runtimes via `agent.delegate`, demultiplexes their event streams,
tolerates per-peer failure.

## Before ARCP

Each peer agent is reached over its own bespoke HTTP/SSE endpoint.
The orchestrator stands up three separate websockets, parses three
different event formats, and writes three retry loops. Trace context
is "added later" and never quite makes it across the seam.

## With ARCP

```python
trace_id = f"trace_{uuid.uuid4().hex[:12]}"
for peer in PEERS:
    job = await delegate(
        client, target=peer.name, task=request, trace_id=trace_id,
    )
    mux.register(job.job_id)

completed = await asyncio.gather(*(collect(mux, j) for j in jobs))
```

One transport, one envelope shape, one trace. Per-peer failure is a
typed `job.failed` envelope, not a 502 with a stack trace.

## ARCP primitives

- `agent.delegate` + `trace_id` propagation — RFC §14, §17.1.
- Job lifecycle (accepted → terminal) — §10.2.
- Stream/event multiplexing across `job_id` — §6.4.

## File tour

- `main.py` — fan-out / gather / synthesize.
- `config.py` — peers + auth.
- `delegation.py` — `agent.delegate` wrapper, returns
  `DelegatedJob`.
- `aggregator.py` — `JobMux` demuxes `client.events()` by
  `job_id` so per-job consumers don't starve each other.

## Variations

- Bound the fan-out by capability (e.g. only peers advertising
  `arcpx.research.web.v1`).
- Return artifact refs from peers (`job.completed.result_ref`)
  instead of inline results when payloads cross the inline budget
  (§16).
- Cancel slowest peer once N succeed via `cancel`
  (see [cancellation](../cancellation)).
