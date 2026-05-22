"""provisioned_credentials server — issues a lease-bound bearer credential (§9.8)."""

from __future__ import annotations

import asyncio
import os

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import (
    ARCPRuntime,
    InMemoryCredentialProvisioner,
    InMemoryRevocationLog,
    JobContext,
    StaticBearerVerifier,
)

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7892"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def model_user(input_value: dict, ctx: JobContext) -> dict:
    model = str(input_value.get("model", "tier-fast/demo"))
    ctx.authorize_model(model)
    await ctx.status("using_model", model)
    return {"model": model, "credential_count": len(ctx.credentials)}


async def main() -> None:
    provisioner = InMemoryCredentialProvisioner()
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="provisioned-credentials-server", version="1.1.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
        credential_provisioner=provisioner,
        revocation_log=InMemoryRevocationLog(),
    )
    runtime.register_agent("model-user", model_user)
    server = await serve_websocket(runtime.accept, host="127.0.0.1", port=PORT, path="/arcp")
    print(f"listening on ws://127.0.0.1:{PORT}/arcp")
    try:
        await asyncio.Future()
    finally:
        print(f"revoked={provisioner.revoked}")
        server.close()
        await server.wait_closed()
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
