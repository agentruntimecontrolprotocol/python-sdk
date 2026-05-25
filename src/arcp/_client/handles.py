"""JobHandle and JobSubscription: client-side observers for a job."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from .._messages.execution import (
    CredentialPayload,
    JobAcceptedPayload,
    JobResultPayload,
    Lease,
    LeaseConstraints,
)


class JobHandle:
    """Client-side handle for a submitted job.

    A handle is created when `ARCPClient.submit` or `ARCPClient.subscribe`
    succeeds. The client read pump pushes inbound events and chunks into
    this handle, and resolves `done` when the terminal `job.result` or
    `job.error` arrives. The handle is automatically released from
    `ARCPClient._handles` on terminal events; consumers do not need to
    take any cleanup action.
    """

    def __init__(self, job_id: str, accepted: JobAcceptedPayload) -> None:
        # MUST be constructed from a running event loop; the SDK only creates
        # `JobHandle` from inside `async def` handlers and tests.
        self.job_id = job_id
        self.accepted = accepted
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._chunks: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        self._terminal: asyncio.Future[JobResultPayload] = loop.create_future()

    @property
    def agent_ref(self) -> str:
        return self.accepted.agent

    @property
    def lease(self) -> Lease:
        return self.accepted.lease

    @property
    def lease_constraints(self) -> LeaseConstraints | None:
        return self.accepted.lease_constraints

    @property
    def budget(self) -> dict[str, str] | None:
        return self.accepted.budget

    @property
    def credentials(self) -> tuple[CredentialPayload, ...]:
        return self.accepted.credentials or ()

    @property
    def trace_id(self) -> str | None:
        return self.accepted.trace_id

    # ---- consumer surface ----------------------------------------------

    @property
    def done(self) -> _DoneAwaitable:
        """Awaitable for the terminal `job.result` payload.

        Resolves with the `JobResultPayload` for `final_status` ∈
        `success`/`cancelled`/`timed_out`, or raises the typed ARCPError
        mapped from a terminal `job.error` envelope.
        """
        return _DoneAwaitable(self._terminal)

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """Async-iterate `job.event` envelope bodies as `{kind, body, ts}` dicts.

        Closes cleanly when the terminal envelope arrives or the client
        closes. `result_chunk` events are routed to `chunks()` instead.
        """
        while True:
            item = await self._events.get()
            if item is None:
                return
            yield item

    async def chunks(self) -> AsyncIterator[dict[str, Any]]:
        """Async-iterate streamed `result_chunk` event bodies.

        Each yielded value is the wire body
        `{result_id, chunk_seq, data, encoding, more}`. Closes when the
        terminal envelope arrives.
        """
        while True:
            item = await self._chunks.get()
            if item is None:
                return
            yield item

    async def collect_chunks(self) -> bytes:
        """Drain `chunks()` and concatenate the decoded application bytes.

        Handles both `utf8` and `base64` chunk encodings transparently.
        Returns the concatenated bytes once the stream is closed.
        """
        out = bytearray()
        async for c in self.chunks():
            data = c.get("data", "")
            enc = c.get("encoding", "utf8")
            if enc == "base64":
                out.extend(base64.b64decode(data))
            else:
                out.extend(data.encode("utf-8") if isinstance(data, str) else data)
        return bytes(out)

    # ---- internal ingest (called by ARCPClient read pump) -------------

    def _push_event(self, body: dict[str, Any]) -> None:
        self._events.put_nowait(body)

    def _push_chunk(self, chunk: dict[str, Any]) -> None:
        self._chunks.put_nowait(chunk)

    def _resolve_terminal(self, payload: JobResultPayload) -> None:
        if not self._terminal.done():
            self._terminal.set_result(payload)
        self._events.put_nowait(None)
        self._chunks.put_nowait(None)

    def _reject_terminal(self, exc: BaseException) -> None:
        if not self._terminal.done():
            self._terminal.set_exception(exc)
        self._events.put_nowait(None)
        self._chunks.put_nowait(None)


class _DoneAwaitable:
    def __init__(self, fut: asyncio.Future[JobResultPayload]) -> None:
        self._fut = fut

    def __await__(self):  # type: ignore[no-untyped-def]
        return self._fut.__await__()


@dataclass
class JobSubscription:
    """Client-side subscription state for `client.subscribe(job_id)`.

    Terminal events for the subscribed job end the subscription
    automatically: the client drops it from its registry before
    resolving the handle. Call `client.unsubscribe(job_id)` only to
    opt out *before* completion.
    """

    job_id: str
    request_id: str
    subscribed_from: int
    replayed: int
    handle: JobHandle


__all__ = ("JobHandle", "JobSubscription")
