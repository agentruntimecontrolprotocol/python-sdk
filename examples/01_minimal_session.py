"""01 — minimal session: open, ping, close.

Demonstrates RFC §8 (handshake) and §6.2 (control plane).
"""

from __future__ import annotations

import asyncio

from _common import runtime_and_client

from arcp.envelope import Envelope


async def main() -> None:
    async with runtime_and_client() as (_, client):
        accepted = await client.open()
        print(f"session opened: {accepted.session_id}")

        ping = Envelope(
            id="msg_ping_1",
            type="ping",
            session_id=accepted.session_id,
            payload={"nonce": "demo"},
        )
        pong = await client.request(ping, timeout=2.0)
        print(f"got {pong.type} with nonce={pong.payload.get('nonce')}")


if __name__ == "__main__":
    asyncio.run(main())
