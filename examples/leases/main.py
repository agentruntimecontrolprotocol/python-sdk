"""Sandboxed on-call agent. Lease-gated shell, reasoning streamed."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from arcp import ARCPClient, ARCPError, ErrorCode

from .agent import LLMStep, llm_loop  # one-shot generator: thought + tool_call

READ_BINARIES = frozenset(
    {"/usr/bin/journalctl", "/usr/bin/cat", "/usr/bin/ss", "/usr/bin/ps"}
)
WRITE_BINARIES = frozenset({"/usr/bin/systemctl", "/usr/bin/kill"})
READ_LEASE_SECONDS = 30 * 60
WRITE_LEASE_SECONDS = 60


def classify(argv: list[str], host: str) -> tuple[str, str, str, int]:
    """Return (permission, resource, operation, lease_seconds)."""
    binary = argv[0]
    if binary in READ_BINARIES:
        return "host.read", f"host:{host}", "read", READ_LEASE_SECONDS
    if binary in WRITE_BINARIES:
        target = argv[2] if binary == "/usr/bin/systemctl" else argv[1]
        return (
            "host.write",
            f"host:{host}/{binary}/{target}",
            "write",
            WRITE_LEASE_SECONDS,
        )
    raise ARCPError(
        ErrorCode.PERMISSION_DENIED, f"binary not allowed: {binary}"
    )


async def acquire_lease(
    client: ARCPClient,
    *,
    permission: str,
    resource: str,
    operation: str,
    seconds: int,
    reason: str,
) -> str:
    reply = await client.request(
        client.envelope(
            "permission.request",
            payload={
                "permission": permission,
                "resource": resource,
                "operation": operation,
                "reason": reason,
                "requested_lease_seconds": seconds,
            },
        ),
        timeout=120.0,
    )
    if reply.type == "permission.deny":
        raise ARCPError(
            ErrorCode.PERMISSION_DENIED,
            str(reply.payload.get("reason") or "denied"),
        )
    return str(reply.payload["lease_id"])


async def run_command(
    client: ARCPClient, argv: list[str], *, reason: str, host: str
) -> str:
    permission, resource, operation, seconds = classify(argv, host)
    lease = await acquire_lease(
        client,
        permission=permission,
        resource=resource,
        operation=operation,
        seconds=seconds,
        reason=reason,
    )
    # The lease is the only guard. Spawn the subprocess elsewhere.
    return f"<would run {argv} under lease {lease}>"


async def emit_thought(
    client: ARCPClient, *, stream_id: str, sequence: int, text: str
) -> None:
    await client.send(
        client.envelope(
            "stream.chunk",
            stream_id=stream_id,
            payload={
                "sequence": sequence,
                "kind": "thought",
                "role": "assistant_thought",
                "content": text,
            },
        )
    )


async def main() -> None:
    client = ARCPClient(...)  # transport, identity (constrained), auth elided
    await client.open()

    stream_id = f"str_{datetime.now(tz=UTC).timestamp():.0f}"
    await client.send(
        client.envelope(
            "stream.open",
            stream_id=stream_id,
            payload={"kind": "thought"},
        )
    )

    seq = 0
    async for step in llm_loop("api-gateway pod is OOMing every 4 minutes"):
        step: LLMStep
        await emit_thought(
            client, stream_id=stream_id, sequence=seq, text=step.thought
        )
        seq += 1
        if step.tool_call is not None:
            try:
                await run_command(
                    client,
                    step.tool_call.argv,
                    reason=step.tool_call.reason,
                    host="edge-pod-04",
                )
            except ARCPError:
                continue  # PERMISSION_DENIED feeds back into the next prompt
        if step.final is not None:
            print(step.final)
            break

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
