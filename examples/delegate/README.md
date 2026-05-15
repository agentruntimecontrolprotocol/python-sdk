# delegate

Demonstrates spec §13.2 / §10: a parent agent submits a child job and the
child inherits the parent's `trace_id`. The parent emits a `delegate`
event carrying `{child_job_id, agent}` so observers can correlate.

## Run

```sh
python examples/delegate/server.py    # terminal 1
python examples/delegate/client.py    # terminal 2
```

Client exits 0 when both parent and child reach `final_status == "success"`
and `child.trace_id == parent.trace_id`.
