"""Warehouse DB admin agent. Reads pre-granted; writes prompt operator."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from arcp import ARCPClient, ARCPError, Envelope, ErrorCode

from .sql import classify  # sqlglot-backed read/write/ddl + tables

PRE_GRANTED = (
    "public.orders",
    "public.customers",
    "warehouse.fct_revenue_daily",
)
READ_LEASE_SECONDS = 60 * 60
WRITE_LEASE_SECONDS = 5 * 60


async def request_lease(
    client: ARCPClient,
    *,
    permission: str,
    table: str,
    operation: str,
    seconds: int,
    reason: str,
) -> tuple[str, datetime]:
    reply = await client.request(
        client.envelope(
            "permission.request",
            payload={
                "permission": permission,
                "resource": f"table:{table}",
                "operation": operation,
                "reason": reason,
                "requested_lease_seconds": seconds,
            },
        ),
        timeout=180.0,
    )
    if reply.type == "permission.deny":
        raise ARCPError(
            ErrorCode.PERMISSION_DENIED, f"{permission} denied on {table}"
        )
    expires = datetime.fromisoformat(
        str(reply.payload["expires_at"]).replace("Z", "+00:00")
    )
    return str(reply.payload["lease_id"]), expires


async def authorize(
    client: ARCPClient,
    sql: str,
    *,
    leases: dict[tuple[str, str], tuple[str, datetime]],
) -> str:
    klass = classify(sql)
    if not klass.tables:
        raise ARCPError(ErrorCode.INVALID_ARGUMENT, "no table referenced")
    op = klass.op  # "read" / "write" / "ddl"
    seconds = READ_LEASE_SECONDS if op == "read" else WRITE_LEASE_SECONDS
    for table in klass.tables:
        cached = leases.get((table, op))
        if cached and cached[1] > datetime.now(tz=UTC):
            continue
        leases[(table, op)] = await request_lease(
            client,
            permission=f"db.{op}",
            table=table,
            operation=op,
            seconds=seconds,
            reason=f"{op.upper()} on {table}: {sql[:80]}",
        )
    return op


def handle_inbound(env: Envelope, leases: dict) -> None:
    """Wire `lease.revoked` into the cache so the next call re-prompts."""
    if env.type == "lease.revoked":
        lid = env.payload.get("lease_id")
        for k, v in list(leases.items()):
            if v[0] == lid:
                leases.pop(k)


async def main() -> None:
    client = ARCPClient(...)  # transport, identity, auth elided
    await client.open()

    leases: dict[tuple[str, str], tuple[str, datetime]] = {}

    async def drain() -> None:
        async for env in client.events():
            handle_inbound(env, leases)

    drain_task = asyncio.create_task(drain())

    # Pre-grant the broad reads at session open. From here on, SELECT
    # against these tables runs free.
    for table in PRE_GRANTED:
        leases[(table, "read")] = await request_lease(
            client,
            permission="db.read",
            table=table,
            operation="read",
            seconds=READ_LEASE_SECONDS,
            reason="bootstrap",
        )

    # SELECT — covered by the bootstrap lease.
    await authorize(
        client,
        "SELECT count(*) FROM public.orders WHERE shipped_at::date = "
        "current_date - 1",
        leases=leases,
    )
    # UPDATE — triggers permission.request; operator must approve.
    await authorize(
        client,
        "UPDATE public.orders SET status='refunded' WHERE id=4812",
        leases=leases,
    )

    drain_task.cancel()
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
