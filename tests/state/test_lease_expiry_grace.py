"""#90 — bounded grace on expires_at enforcement and lease-expiry audit logging (§14)."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
from typing import Any

import pytest

from arcp import (
    Capabilities,
    ClientInfo,
    LeaseConstraints,
    LeaseExpiredError,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._messages.execution import LeaseConstraints as LC
from arcp._runtime.lease import LeaseOpContext, validate_lease_op
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


def test_expiry_grace_window_is_applied_and_configurable() -> None:
    now = dt.datetime.now(dt.UTC)
    # expires_at 0.5s in the past relative to `now`.
    expires = (now - dt.timedelta(seconds=0.5)).isoformat().replace("+00:00", "Z")
    constraints = LC(expires_at=expires)
    lease = {"fs.read": ["*"]}
    ctx = LeaseOpContext(capability="fs.read", target="f", now=now)

    # Within a 1s grace window -> still authorized.
    validate_lease_op(lease, ctx, constraints=constraints, grace_sec=1.0)

    # Grace disabled -> expired.
    with pytest.raises(LeaseExpiredError):
        validate_lease_op(lease, ctx, constraints=constraints, grace_sec=0.0)


class _CapturingLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, Any]]] = []

    def bind(self, **_kw: Any) -> _CapturingLogger:
        return self

    def info(self, event: str, **kw: Any) -> None:
        self.records.append((event, kw))

    def warning(self, *_a: Any, **_k: Any) -> None: ...
    def error(self, *_a: Any, **_k: Any) -> None: ...
    def debug(self, *_a: Any, **_k: Any) -> None: ...
    def exception(self, *_a: Any, **_k: Any) -> None: ...


async def test_lease_expiration_is_logged_for_audit() -> None:
    logger = _CapturingLogger()
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
        lease_expiry_grace_sec=0.1,
        logger=logger,
    )

    async def slow(input_value, ctx):
        await asyncio.sleep(5.0)
        return "never"

    rt.register_agent("slow", slow)

    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    await client.connect(client_t)
    try:
        expiry = (dt.datetime.now(dt.UTC) + dt.timedelta(milliseconds=100)).isoformat()
        handle = await client.submit(
            agent="slow",
            lease_request={"fs.read": ["/tmp/*"]},
            lease_constraints=LeaseConstraints(expires_at=expiry.replace("+00:00", "Z")),
        )
        with pytest.raises(LeaseExpiredError):
            await asyncio.wait_for(handle.done, timeout=3.0)
        assert any(event == "lease_expired" for event, _ in logger.records), logger.records
    finally:
        with contextlib.suppress(Exception):
            await client.close()
        accept_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await accept_task
        await rt.close()
