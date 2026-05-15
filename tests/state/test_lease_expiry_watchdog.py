"""§13.4 — lease expiry watchdog emits LEASE_EXPIRED."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from arcp import LeaseConstraints, LeaseExpiredError
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime


async def test_lease_expires_triggers_error(runtime: ARCPRuntime, client: ARCPClient) -> None:
    async def slow(input_value, ctx):
        await asyncio.sleep(2.0)
        return "never"

    runtime.register_agent("slow-lease", slow)
    # Expire ~150ms in the future
    expiry = (datetime.now(UTC) + timedelta(milliseconds=150)).isoformat()
    expiry = expiry.replace("+00:00", "Z")
    handle = await client.submit(
        agent="slow-lease",
        lease_request={"fs.read": ["/tmp/*"]},
        lease_constraints=LeaseConstraints(expires_at=expiry),
    )
    with pytest.raises(LeaseExpiredError):
        await handle.done
