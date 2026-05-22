# Email Vendor Leases

This recipe shows how to attach vendor-specific lease fields to a job using
`x-*` extensions (spec [§15](https://arcp.dev/spec/v1.1#section-15)) alongside
the standard cost budget (spec [§9](https://arcp.dev/spec/v1.1#section-9)) to
enforce per-job email-sending limits.

## Use-case

Your agent sends transactional emails through a third-party provider (e.g.,
SendGrid, Postmark).  You want to:

* Cap the dollar cost of a single job.
* Cap the number of email messages the job may send.
* Expose the remaining quota back to the caller through structured events.

The cost budget is a first-class ARCP concept; the email quota is represented
as a vendor extension field (`x-email-max-messages`) that your runtime
evaluates and your agent reads from `ctx.lease`.

## Server

```python
import asyncio
from decimal import Decimal
from arcp import ARCPRuntime, JobContext
from arcp.auth import StaticBearerVerifier
from arcp.transport import pair_memory_transports

MAX_EMAILS = 50


async def email_agent(ctx: JobContext) -> None:
    # Read the vendor extension from the negotiated lease.
    raw = ctx.lease.extensions.get("x-email-max-messages")
    email_budget = int(raw) if raw is not None else MAX_EMAILS
    sent = 0

    async for item in ctx.input_stream():
        if sent >= email_budget:
            await ctx.emit_event(
                "vendor.email.quota_exceeded",
                {"sent": sent, "limit": email_budget},
            )
            await ctx.cancel("email quota reached")
            return

        # Simulate sending an email.
        recipient = item.get("to", "")
        await _send_email(recipient, item)
        sent += 1
        await ctx.emit_event(
            "vendor.email.sent",
            {
                "to": recipient,
                "sent": sent,
                "remaining": email_budget - sent,
            },
        )

    await ctx.emit_event("vendor.email.summary", {"total_sent": sent})


async def _send_email(to: str, payload: dict) -> None:
    """Placeholder — swap in your actual provider SDK call."""
    await asyncio.sleep(0.01)


server_transport, client_transport = pair_memory_transports()

runtime = ARCPRuntime(
    transport=server_transport,
    auth=StaticBearerVerifier("secret"),
)
runtime.register_agent("email", email_agent)
```

## Client — submitting with vendor lease extensions

```python
from arcp import ARCPClient
from arcp.models import CostBudget, Lease


async def main() -> None:
    async with ARCPClient(client_transport, token="secret") as client:
        handle = await client.submit(
            agent="email",
            input=[
                {"to": "alice@example.com", "subject": "Hello", "body": "Hi!"},
                {"to": "bob@example.com", "subject": "Hello", "body": "Hi!"},
            ],
            lease=Lease(
                cost_budget=CostBudget(usd=Decimal("0.50")),
                extensions={
                    # Vendor field: cap this job at 10 emails.
                    "x-email-max-messages": "10",
                },
            ),
        )

        async for event in handle.events():
            kind = event.kind
            if kind == "vendor.email.sent":
                print(
                    f"Sent to {event.data['to']} "
                    f"({event.data['remaining']} remaining)"
                )
            elif kind == "vendor.email.quota_exceeded":
                print(f"Quota exceeded after {event.data['sent']} emails")
            elif kind == "vendor.email.summary":
                print(f"Done — total sent: {event.data['total_sent']}")

        await handle.done


asyncio.run(main())
```

## How it works

| Layer | Mechanism |
|---|---|
| Cost budget | `Lease.cost_budget` — enforced natively by the runtime (spec §9) |
| Email quota | `Lease.extensions["x-email-max-messages"]` — enforced by the agent |
| Quota events | `vendor.email.*` — structured events consumed by the caller |

`x-*` extension fields are passed through unchanged; the runtime does not
interpret them.  The naming convention `x-<vendor>-<field>` avoids collisions
with future ARCP spec additions (spec §15.2).

## Related

- [Leases guide](../guides/leases.md)
- [Vendor extensions guide](../guides/vendor-extensions.md)
- [Cost budget recipe](cost-budget.md)
- [Lease violation recipe](lease-violation.md)
