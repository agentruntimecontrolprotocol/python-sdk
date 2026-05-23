"""stream-resume client — disconnect mid-stream, reconnect, assemble across the gap.

Demonstrates the disconnect → resume → assemble flow over a chunked
streaming result. Session 1 connects, submits, and starts receiving
result_chunk events; the transport is then dropped mid-stream
(without session.bye, so the session id stays valid for the runtime's
resume window). Session 2 calls client.resume() with the rotated
resume_token + the last event_seq we observed, the runtime replays
every envelope with seq > last_event_seq from its EventLog, and we
reassemble the article from the union of what both sessions saw.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import os
import sys

from arcp import ClientInfo, SessionResume, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7901"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


def _new_client() -> ARCPClient:
    return ARCPClient(
        client=ClientInfo(name="writer-client", version="1.0.0"),
        token=TOKEN,
        features=("result_chunk",),
    )


def _record(chunks: dict[int, str], body: dict) -> None:
    # in a real client you would dedupe by chunk_seq because the resume
    # replay may overlap with chunks session 1 already saw — the dict
    # insertion handles that naturally below.
    data = body.get("data", "")
    if body.get("encoding") == "base64":
        data = base64.b64decode(data).decode("utf-8", errors="replace")
    chunks[body["chunk_seq"]] = data


async def main() -> int:
    chunks: dict[int, str] = {}

    # ── session 1: submit, observe a prefix of chunks, then drop ────────
    first = _new_client()
    transport1 = await WebSocketTransport.connect(URL)
    welcome1 = await first.connect(transport1)
    handle = await first.submit(agent="long-form", input={"topic": "urban heat islands"})

    seen = 0
    async for chunk in handle.chunks():
        _record(chunks, chunk)
        seen += 1
        if seen >= 3:
            break
    last_seq = first.latest_event_seq
    # drop transport WITHOUT calling client.close() so we don't send session.bye —
    # the session id stays valid for resume_window_sec
    await transport1.close()
    print(f"session 1 saw {seen} chunks; dropping transport at seq={last_seq}")

    # ── session 2: resume with the session id + rotated token + lastSeq ─
    second = _new_client()
    async with contextlib.aclosing(second):
        transport2 = await WebSocketTransport.connect(URL)
        await second.resume(
            transport2,
            resume=SessionResume(
                session_id=welcome1.session_id,
                resume_token=welcome1.resume_token,
                last_event_seq=last_seq,
            ),
        )
        # resume re-establishes the session; subscribe to the original job id
        # with from_event_seq so the runtime replays the chunk tail.
        sub = await second.subscribe(handle.job_id, from_event_seq=last_seq)
        async for chunk in sub.handle.chunks():
            _record(chunks, chunk)
        await sub.handle.done

    # assemble the article from chunks ordered by chunk_seq. dict dedup is
    # what handles the resume boundary — if session 1 saw chunk_seq 3 and
    # the runtime replays 3 again, the second write just overwrites.
    article = "".join(data for _, data in sorted(chunks.items()))
    print(f"reassembled {len(article)} chars across {len(chunks)} chunks")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
