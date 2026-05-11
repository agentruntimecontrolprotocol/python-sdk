# permission_challenge

Two-agent loop. Generator proposes patches; reviewer holds veto on
the `apply_patch` step via `permission.request`. Denied patches feed
back into the generator with the reviewer's reason. Bounded retry.

## Before ARCP

Either (a) the reviewer is a post-hoc filter that cannot say no with
authority — the generator already moved on; or (b) a custom
agent-to-agent RPC the two sides reimplement and re-bug every
quarter. Neither produces a typed audit trail of "what was approved,
when, and why".

## With ARCP

```python
# generator side
lease = await request_apply(client, ticket_id=ticket, patch=patch)

# reviewer side
async for env in client.events():
    if env.type == "permission.request":
        verdict = await agents.review(ticket=ticket, patch=...)
        await respond(client, request=env, verdict=verdict)
```

Two separate sessions. Same envelope contract. The reviewer's "no"
arrives at the generator as a structured `PERMISSION_DENIED` with a
`reason` field, not a 403 with a stack trace.

## ARCP primitives

- Permission challenge — RFC §15.4.
- Lease materialization — §15.5 (`lease.granted`).
- Structured errors — §18 (`PERMISSION_DENIED` for veto,
  `FAILED_PRECONDITION` for content-driven denial).
- `idempotency_key` per (ticket, diff) — §6.4.

## File tour

- `main.py` — bounded loop. Two sessions, one process for the demo.
- `config.py` — endpoint + auth + retry cap.
- `agents.py` — `propose` and `review` stubs (LLM elided).
- `review_gate.py` — `request_apply` + `respond`. The interesting
  file.
- `patches.py` — `Patch` model + idempotency-key derivation.

## Variations

- Three agents (security + style + correctness reviewers); the
  runtime gates `permission.grant` until all three respond.
- Stream test runner output as `kind: text` between attempts so the
  reviewer can see what broke.
- Promote denied patches into a learning corpus via `event.emit`.
