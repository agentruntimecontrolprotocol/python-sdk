"""Subscription engine (RFC §13)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

import structlog

from arcp.envelope import Envelope
from arcp.errors import ARCPError, ErrorCode
from arcp.messages.subscriptions import (
    BACKFILL_COMPLETE_TYPE,
    SubscribeFilter,
    SubscribePayload,
    SubscribeSince,
    SubscriptionBackfillCompletePayload,
)
from arcp.store.eventlog import EventLog

logger = structlog.get_logger("arcp.subscription")

PRIORITY_RANK: dict[str, int] = {"low": 0, "normal": 1, "high": 2, "critical": 3}


def _passes_filter(envelope: Envelope, filt: SubscribeFilter) -> bool:
    """Apply §13.2 filter semantics: AND across fields, OR within arrays."""

    if filt.session_id and envelope.session_id not in filt.session_id:
        return False
    if filt.trace_id and (envelope.trace_id is None or envelope.trace_id not in filt.trace_id):
        return False
    if filt.job_id and (envelope.job_id is None or envelope.job_id not in filt.job_id):
        return False
    if filt.stream_id and (envelope.stream_id is None or envelope.stream_id not in filt.stream_id):
        return False
    if filt.types and envelope.type not in filt.types:
        return False
    if filt.min_priority is not None:
        if PRIORITY_RANK[envelope.priority] < PRIORITY_RANK[filt.min_priority]:
            return False
    return True


@dataclass
class Subscription:
    subscription_id: str
    subscriber_session_id: str
    filter: SubscribeFilter
    queue: asyncio.Queue[Envelope | None] = field(
        default_factory=lambda: asyncio.Queue[Envelope | None]()
    )
    closed: bool = False
    backfill_done: bool = False
    backfill_count: int = 0


@dataclass
class SubscriptionManager:
    """Per-runtime subscription registry.

    Subscriptions are owned by a *subscriber* session. The runtime invokes
    :meth:`broadcast` after every event log append; the manager fans the
    envelope out to interested subscriptions.
    """

    event_log: EventLog
    _subscriptions: dict[str, Subscription] = field(default_factory=dict[str, Subscription])
    _backfill_tasks: set[asyncio.Task[None]] = field(default_factory=set[asyncio.Task[None]])

    def all(self) -> list[Subscription]:
        return list(self._subscriptions.values())

    def get(self, subscription_id: str) -> Subscription:
        sub = self._subscriptions.get(subscription_id)
        if sub is None:
            raise ARCPError(ErrorCode.NOT_FOUND, f"subscription {subscription_id!r} not found")
        return sub

    async def subscribe(
        self,
        *,
        subscriber_session_id: str,
        payload: SubscribePayload,
        is_authorized: Callable[[SubscribeFilter], None],
    ) -> Subscription:
        """Open a new subscription. ``is_authorized(filter)`` may raise to reject."""

        is_authorized(payload.filter)
        sub = Subscription(
            subscription_id=f"sub_{uuid.uuid4().hex[:12]}",
            subscriber_session_id=subscriber_session_id,
            filter=payload.filter,
        )
        self._subscriptions[sub.subscription_id] = sub
        if payload.since is not None:
            self._backfill_tasks.add(asyncio.create_task(self._backfill(sub, payload.since)))
        else:
            sub.backfill_done = True
        return sub

    async def _backfill(self, sub: Subscription, since: SubscribeSince) -> None:
        async for env in self.event_log.replay(after_message_id=since.after_message_id):
            if sub.closed:
                return
            if _passes_filter(env, sub.filter):
                sub.backfill_count += 1
                await sub.queue.put(env)
        if sub.closed:
            return
        marker = Envelope(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            type=BACKFILL_COMPLETE_TYPE,
            subscription_id=sub.subscription_id,
            payload=SubscriptionBackfillCompletePayload(
                subscription_id=sub.subscription_id,
                event_count=sub.backfill_count,
            ).model_dump(),
        )
        sub.backfill_done = True
        await sub.queue.put(marker)

    async def broadcast(self, envelope: Envelope) -> None:
        """Fan ``envelope`` out to every matching subscription's live tail."""

        for sub in self._subscriptions.values():
            if sub.closed or not sub.backfill_done:
                continue
            if not _passes_filter(envelope, sub.filter):
                continue
            await sub.queue.put(envelope)

    async def close(self, subscription_id: str) -> Subscription:
        sub = self.get(subscription_id)
        sub.closed = True
        await sub.queue.put(None)
        return sub


__all__ = ["PRIORITY_RANK", "Subscription", "SubscriptionManager"]
