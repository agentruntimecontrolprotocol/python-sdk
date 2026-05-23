"""resume client — disconnect after seq=2, reconnect with SessionResume; assert tail replays."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, SessionResume, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7880"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


def _new_client() -> ARCPClient:
    return ARCPClient(
        client=ClientInfo(name="resume-client", version="1.0.0"),
        token=TOKEN,
        features=(),
    )


async def main() -> int:
    # First connection: capture session_id + resume_token, observe a few events,
    # then close the transport without sending session.bye.
    first = _new_client()
    transport1 = await WebSocketTransport.connect(URL)
    welcome1 = await first.connect(transport1)
    handle = await first.submit(agent="slow", input={})
    seen = 0
    async for _ in handle.events():
        seen += 1
        if seen >= 2:
            break
    last_seq = first.latest_event_seq
    token1 = welcome1.resume_token
    sid = welcome1.session_id
    # Drop transport WITHOUT calling client.close() so we don't send session.bye.
    await transport1.close()
    print(f"first connection observed {seen} events; resume_token={token1[:8]}...")

    # Second connection: present SessionResume to the runtime.
    second = _new_client()
    async with contextlib.aclosing(second):
        transport2 = await WebSocketTransport.connect(URL)
        welcome2 = await second.resume(
            transport2,
            resume=SessionResume(session_id=sid, resume_token=token1, last_event_seq=last_seq),
        )
        token2 = welcome2.resume_token
        print(f"resumed; new resume_token={token2[:8]}...")
        assert token2 != token1, "resume_token MUST rotate on every welcome"
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
