# Vendor extensions

> Spec reference: ARCP v1.1 §15

**Vendor extensions** allow clients, agents, and runtimes to attach arbitrary metadata to ARCP messages using `x-*` prefixed fields. The SDK passes them through without modification.

## Sending extensions from the client

Pass `extensions` to `client.submit()`:

```python
handle = await client.submit(
    agent="send-email",
    input={"to": "alice@example.com", "body": "Hello!"},
    extensions={
        "x-vendor-campaign-id": "camp-2025-q1",
        "x-vendor-tracking-pixel": True,
    },
)
```

## Reading extensions in an agent

```python
from arcp import get_extension

async def send_email(input, ctx):
    campaign_id = get_extension(ctx, "x-vendor-campaign-id")
    tracking = get_extension(ctx, "x-vendor-tracking-pixel", default=False)

    await send(
        to=input["to"],
        body=input["body"],
        campaign_id=campaign_id,
        tracking_pixel=tracking,
    )
    return {"sent": True}
```

## Sending extensions from an agent

Agents can attach `x-*` fields to job events:

```python
async def send_email(input, ctx):
    message_id = await send(input["to"], input["body"])
    return {
        "sent": True,
        "x-vendor-message-id": message_id,
        "x-vendor-delivery-status": "queued",
    }
```

## Reading extensions from events

```python
from arcp import get_extension

async for event in handle.events():
    if event.kind == "job.completed":
        msg_id = get_extension(event, "x-vendor-message-id")
        print(f"Message ID: {msg_id}")
```

## Extension naming conventions

- Always prefix with `x-` followed by a vendor slug: `x-acme-`, `x-myco-`
- Use lowercase kebab-case: `x-acme-retry-count`, not `x-Acme-RetryCount`
- Document extensions in your API reference so clients know what to expect

## Extension validation

The SDK does not validate extension values. If you need typed extensions, validate them in your agent function:

```python
async def my_agent(input, ctx):
    raw = get_extension(ctx, "x-acme-config")
    config = AcmeConfig.model_validate(raw) if raw else AcmeConfig()
    ...
```

## Related

- [Email vendor leases recipe](../recipes/email-vendor-leases.md)
- [Architecture](../architecture.md) — `arcp/_extensions.py`
