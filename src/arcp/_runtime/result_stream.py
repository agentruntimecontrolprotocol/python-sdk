"""Chunked-result writer used by agents (spec §8.4)."""

from __future__ import annotations

import base64
import datetime as dt
from types import TracebackType
from typing import TYPE_CHECKING, Literal, Self

from .._errors import InvalidRequestError
from .._logger import get_logger
from .._messages.execution import JobResultPayload

if TYPE_CHECKING:
    from .job import JobContext


_LOG = get_logger("arcp.runtime.result_stream")


def _now_iso_z() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


class ResultStream:
    """Async-context-manager writer for §8.4 chunked results.

    `result_size` on the terminal `job.result` envelope reports the byte
    length of the *decoded application data* written through `write()`:
    for `bytes` inputs it is `len(data)`, for `str` inputs it is the UTF-8
    byte length. This makes `result_size` directly comparable to
    `len(handle.collect_chunks())` on the client side regardless of whether
    the payload travelled as base64 or utf8 on the wire.
    """

    def __init__(self, ctx: JobContext, *, result_id: str) -> None:
        self._ctx = ctx
        self._result_id = result_id
        self._chunk_seq = 0
        self._closed = False
        self._total_size = 0

    @property
    def result_id(self) -> str:
        return self._result_id

    async def write(
        self,
        data: bytes | str,
        *,
        encoding: Literal["utf8", "base64"] | None = None,
    ) -> None:
        if self._closed:
            raise InvalidRequestError("ResultStream already closed")
        # Track size of decoded application data, not the encoded wire payload.
        data_len = len(data) if isinstance(data, bytes) else len(data.encode("utf-8"))
        if isinstance(data, bytes):
            payload = base64.b64encode(data).decode("ascii")
            enc: Literal["utf8", "base64"] = "base64"
        else:
            payload = data
            enc = encoding or "utf8"
        body = {
            "result_id": self._result_id,
            "chunk_seq": self._chunk_seq,
            "data": payload,
            "encoding": enc,
            "more": True,
        }
        await self._ctx.result_chunk(body)
        self._chunk_seq += 1
        self._total_size += data_len

    async def close(self, *, summary: str | None = None) -> None:
        """Send a final `more=False` chunk (empty) and a terminal `job.result`."""
        if self._closed:
            return
        self._closed = True
        await self._ctx.result_chunk(
            {
                "result_id": self._result_id,
                "chunk_seq": self._chunk_seq,
                "data": "",
                "encoding": "utf8",
                "more": False,
            }
        )
        await self._ctx.job.emit_result(
            JobResultPayload(
                final_status="success",
                result_id=self._result_id,
                result_size=self._total_size,
                summary=summary,
                completed_at=_now_iso_z(),
            )
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self._closed:
            try:
                await self.close()
            except Exception:
                _LOG.exception("result_stream_close_failed")


__all__ = ("ResultStream",)
