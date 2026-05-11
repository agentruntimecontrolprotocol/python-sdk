"""Two scenarios over the §10.4 / §10.5 control surface."""

from __future__ import annotations

import asyncio
import sys

from arcp import ARCPClient, ARCPError, Envelope, ErrorCode

CANCEL_DEADLINE_MS = 5_000


async def start_long_job(client: ARCPClient) -> str:
    accepted = await client.request(
        client.envelope(
            "tool.invoke",
            payload={
                "tool": "demo.long_running",
                "arguments": {"work_seconds": 600},
            },
        ),
        timeout=10.0,
    )
    return str(accepted.payload["job_id"])


async def cancel_job(
    client: ARCPClient, *, job_id: str, reason: str, deadline_ms: int
) -> Envelope:
    """Cooperative cancel. Runtime drives target to a clean checkpoint
    inside `deadline_ms` before terminating; escalates to ABORTED on
    timeout (RFC §10.4)."""
    reply = await client.request(
        client.envelope(
            "cancel",
            payload={
                "target": "job",
                "target_id": job_id,
                "reason": reason,
                "deadline_ms": deadline_ms,
            },
        ),
        timeout=deadline_ms / 1000 + 5,
    )
    if reply.type == "cancel.refused":
        raise ARCPError(
            ErrorCode.FAILED_PRECONDITION,
            str(reply.payload.get("reason") or "cancel refused"),
        )
    return reply


async def interrupt_job(
    client: ARCPClient, *, job_id: str, prompt: str
) -> None:
    """Distinct from cancel: pauses the job (`blocked`), runtime emits
    `human.input.request`. Job is NOT terminated (RFC §10.5)."""
    await client.send(
        client.envelope(
            "interrupt",
            payload={
                "target": "job",
                "target_id": job_id,
                "prompt": prompt,
            },
        )
    )


async def await_terminal(client: ARCPClient, *, job_id: str) -> Envelope:
    async for env in client.events():
        if env.job_id != job_id:
            continue
        if env.type in {"job.completed", "job.failed", "job.cancelled"}:
            return env
    raise RuntimeError("event stream closed before terminal")


async def scenario_cancel() -> None:
    client = ARCPClient(...)  # transport, identity, auth elided
    await client.open()
    try:
        job_id = await start_long_job(client)
        await asyncio.sleep(2)  # let the job actually start
        ack = await cancel_job(
            client,
            job_id=job_id,
            reason="user_aborted",
            deadline_ms=CANCEL_DEADLINE_MS,
        )
        print(f"cancel ack: {ack.type}")
        terminal = await await_terminal(client, job_id=job_id)
        print(f"terminal: {terminal.type} code={terminal.payload.get('code')}")
    finally:
        await client.close()


async def scenario_interrupt() -> None:
    client = ARCPClient(...)
    await client.open()
    try:
        job_id = await start_long_job(client)
        await asyncio.sleep(2)
        await interrupt_job(
            client,
            job_id=job_id,
            prompt="Pause and ask before touching production tables.",
        )
        # Runtime now emits human.input.request; answer via examples/human_input.
        async for env in client.events():
            if env.type == "human.input.request" and env.job_id == job_id:
                print(f"awaiting human: {env.payload.get('prompt')!r}")
                return
    finally:
        await client.close()


async def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "cancel"
    if which == "cancel":
        await scenario_cancel()
    elif which == "interrupt":
        await scenario_interrupt()
    else:
        raise SystemExit(f"unknown scenario: {which}")


if __name__ == "__main__":
    asyncio.run(main())
