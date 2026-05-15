# idempotent_retry

Demonstrates spec §13.5 / §7.2: a second submit with the same
`(principal, idempotency_key)` replays the original `job.accepted`
verbatim, but a third submit reusing the key with a different `agent`
raises `DuplicateKeyError`.

## Run

```sh
python examples/idempotent_retry/server.py    # terminal 1
python examples/idempotent_retry/client.py    # terminal 2
```

Client exits 0 when the retry returns the original `job_id` and the
mutated submit raises `DuplicateKeyError`.
