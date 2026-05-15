# resume

Demonstrates spec §13.3 / §6.3: client disconnects after observing a
couple of events, then reconnects with `session.hello.payload.resume =
{session_id, resume_token, last_event_seq}`. The runtime issues a fresh
`resume_token` on the new welcome.

## Run

```sh
python examples/resume/server.py    # terminal 1
python examples/resume/client.py    # terminal 2
```

Client exits 0 when the second connection's `resume_token` differs from
the first's.
