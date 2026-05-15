"""vendor_extensions client — naïve and vendor-aware handlers, side-by-side."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7884"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


def naive_handler(kind: str, body: dict) -> bool:
    """Match only on reserved kinds; unknown kinds are silently dropped."""
    match kind:
        case "status":
            print(f"[naive] status: {body.get('phase')}")
            return False
    return True  # this kind was dropped


def vendor_handler(kind: str, body: dict) -> bool:
    """Vendor-aware: render x-vendor.acme.* before falling back."""
    if kind.startswith("x-vendor.acme."):
        print(f"[acme] {kind}: {body}")
        return False
    return naive_handler(kind, body)


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="vendor-extensions-client", version="1.0.0"),
        token=TOKEN,
        features=(),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        # Request a vendor lease namespace alongside a reserved one.
        handle = await client.submit(
            agent="vendor",
            input={},
            lease_request={"x-vendor.acme.metrics": ["*"]},
        )
        naive_dropped = 0
        vendor_rendered = 0
        async for ev in handle.events():
            if naive_handler(ev["kind"], ev["body"]):
                naive_dropped += 1
            if not vendor_handler(ev["kind"], ev["body"]):
                if ev["kind"].startswith("x-vendor.acme."):
                    vendor_rendered += 1
        result = await handle.done
        print(
            f"terminal: {result.final_status}; naive_dropped={naive_dropped}, vendor_rendered={vendor_rendered}"
        )
        assert naive_dropped >= 1, "naïve handler was supposed to drop unknown kinds"
        assert vendor_rendered >= 1, "vendor handler was supposed to render acme events"
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
