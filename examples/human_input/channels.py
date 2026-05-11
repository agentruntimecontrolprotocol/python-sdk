"""Per-destination channel adapters. Real versions wrap ntfy.sh,
SES, and the Slack web API. Each returns a value matching the
request's `response_schema`."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

ChannelResponse = Callable[
    [str, dict[str, object]], Awaitable[dict[str, object]]
]


async def ntfy_phone(prompt: str, schema: dict[str, object]) -> dict:
    raise NotImplementedError


async def email_oncall(prompt: str, schema: dict[str, object]) -> dict:
    raise NotImplementedError


async def slack_ops(prompt: str, schema: dict[str, object]) -> dict:
    raise NotImplementedError


REGISTRY: dict[str, ChannelResponse] = {
    "ntfy:phone": ntfy_phone,
    "email:oncall": email_oncall,
    "slack:ops": slack_ops,
}
