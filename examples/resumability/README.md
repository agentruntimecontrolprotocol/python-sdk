# resumability

Five-step research job (plan → gather → synthesize → critique →
finalize) that checkpoints after every step. Crash mid-flight,
resume on next invocation, no work lost.

## Before ARCP

Long jobs survive crashes only if the team built their own
checkpoint store, retry contract, and dedupe layer. Most don't.
Crash means restart; restart means re-spending tokens; "did this
already run?" turns into a SQL detective story.

## With ARCP

```python
# every step ends with two envelopes
await emit_progress(client, job_id=..., step="synthesize", percent=60)
await emit_checkpoint(client, job_id=..., step="synthesize")

# resume picks up at the step *after* the last checkpoint
state = await consume_replay(client, job_id=settings.resume_job_id)
next_idx = STEPS.index(state.last_checkpoint_label) + 1
```

Per-step `idempotency_key` keeps execution single across retries:
the runtime returns the prior outcome if the same step is re-issued.

## Try it

```bash
# crash after `synthesize`. Prints the resume token.
CRASH_AFTER_STEP=synthesize \
  python -m examples.resumability.main

# resume — runtime replays up to the last checkpoint, we run from
# the next step.
RESUME_JOB_ID=...  RESUME_AFTER_MSG_ID=...  RESUME_CHECKPOINT_ID=... \
  python -m examples.resumability.main
```

## ARCP primitives

- Resumability — RFC §19, `after_message_id` + `checkpoint_id`.
- Job lifecycle + checkpoints — §10.
- `idempotency_key` semantics — §6.4.
- `DATA_LOSS` on retention expiry — §19, §18.2.

## File tour

- `main.py` — `start_fresh` vs `resume`. `os._exit` on the crash
  step to demonstrate process death.
- `config.py` — endpoint, step list, resume + crash env vars.
- `steps.py` — emit_progress / emit_checkpoint / derive_key.
  Actual step body is stubbed.
- `idem.py` — deterministic per-step idempotency keys.
- `resume.py` — issues `resume`, drains replay, finds the
  checkpoint to continue from.

## Variations

- Plug a LangGraph checkpointer that doubles to a SQLite store so
  checkpoints survive ARCP retention expiry too.
- Branch on critique severity: low → finalize; high → loop back to
  synthesize with the critique appended.
- Emit `kind: thought` between steps for
  [reasoning_streams](../reasoning_streams) to consume.
