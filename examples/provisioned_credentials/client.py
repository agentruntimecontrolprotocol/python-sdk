"""provisioned_credentials client — reads credentials from job.accepted."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7892"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def main() -> int:
    client = ARCPClient(
        client=ClientInfo(name="provisioned-credentials-client", version="1.1.0"),
        token=TOKEN,
        features=("model.use", "provisioned_credentials", "cost.budget"),
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect(URL)
        await client.connect(transport)
        handle = await client.submit(
            agent="model-user",
            input={"model": "tier-fast/demo"},
            lease_request={
                "model.use": ["tier-fast/*"],
                "cost.budget": ["USD:1.00"],
            },
        )
        credential = handle.credentials[0]
        print(
            f"credential id={credential.id} scheme={credential.scheme} endpoint={credential.endpoint}"
        )
        result = await handle.done
        assert result.final_status == "success"
        assert result.result == {"model": "tier-fast/demo", "credential_count": 1}
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
