"""Durable research job with real crash and resume.

    # First call: crash after `synthesize`. Prints the resume token.
    CRASH_AFTER_STEP=synthesize \
      python -m examples.resumability.main

    # Second call: pick up from the printed checkpoint.
    RESUME_JOB_ID=...  RESUME_AFTER_MSG_ID=...  RESUME_CHECKPOINT_ID=... \
      python -m examples.resumability.main
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid

from arcp import ARCPClient, ARCPError, ErrorCode

from .steps import run_step  # plan / gather / synthesize / critique / finalize

STEPS = ("plan", "gather", "synthesize", "critique", "finalize")


def step_key(*, job_id: str, step: str, salt: str) -> str:
    """Deterministic per-step idempotency key (RFC §6.4). Re-issuing
    the same step with the same input returns the prior outcome
    instead of re-running the LLM."""
    h = hashlib.sha256()
    for piece in (job_id, step, salt):
        h.update(piece.encode())
        h.update(b"\x00")
    return f"research:{job_id}:{step}:{h.hexdigest()[:16]}"


async def emit_progress(client: ARCPClient, *, job_id: str, step: str) -> None:
    pct = 100.0 * (STEPS.index(step) + 1) / len(STEPS)
    await client.send(
        client.envelope(
            "job.progress",
            job_id=job_id,
            payload={"percent": pct, "message": step},
        )
    )


async def emit_checkpoint(client: ARCPClient, *, job_id: str, step: str) -> str:
    chk = f"chk_{step}_{job_id[-6:]}"
    await client.send(
        client.envelope(
            "job.checkpoint",
            job_id=job_id,
            payload={"checkpoint_id": chk, "label": step},
        )
    )
    return chk


async def execute_steps(
    client: ARCPClient,
    *,
    job_id: str,
    request: object,
    starting_at: str,
    crash_after: str | None,
) -> object:
    output = request
    for step in STEPS:
        if STEPS.index(step) < STEPS.index(starting_at):
            continue
        key = step_key(job_id=job_id, step=step, salt=repr(output))
        await emit_progress(client, job_id=job_id, step=step)
        output = await run_step(
            client,
            job_id=job_id,
            step=step,
            inputs={"prior": output, "idempotency_key": key},
        )
        await emit_checkpoint(client, job_id=job_id, step=step)
        if crash_after == step:
            # The whole point of durable jobs: process death is fine.
            # Runtime kept every envelope; resume picks it up.
            print(
                f"[crash after {step}; resume with "
                f"RESUME_JOB_ID={job_id} "
                f"RESUME_CHECKPOINT_ID=chk_{step}_{job_id[-6:]} "
                f"RESUME_AFTER_MSG_ID=<last id from your event log>]"
            )
            os._exit(137)
    return output


async def issue_resume(
    client: ARCPClient,
    *,
    job_id: str,
    after_message_id: str,
    checkpoint_id: str | None,
) -> str | None:
    """Replay envelopes; return the last checkpoint label, or None
    if the job already terminated during replay."""
    payload: dict[str, object] = {
        "after_message_id": after_message_id,
        "include_open_streams": True,
    }
    if checkpoint_id:
        payload["checkpoint_id"] = checkpoint_id
    await client.send(client.envelope("resume", job_id=job_id, payload=payload))

    last: str | None = None
    async for env in client.events():
        if env.job_id != job_id:
            continue
        if env.type == "tool.error" and env.payload.get("code") == str(
            ErrorCode.DATA_LOSS
        ):
            raise ARCPError(ErrorCode.DATA_LOSS, "retention expired")
        if env.type == "job.checkpoint":
            last = str(env.payload.get("label"))
        elif env.type in {"job.completed", "job.failed", "job.cancelled"}:
            return None
        elif (
            env.type == "event.emit"
            and env.payload.get("name") == "subscription.backfill_complete"
        ):
            return last  # replay window closed; we're now live
    return last


async def main() -> None:
    client = ARCPClient(...)  # transport, identity, auth elided
    await client.open()

    rj_id = os.environ.get("RESUME_JOB_ID")
    rj_after = os.environ.get("RESUME_AFTER_MSG_ID")
    if rj_id and rj_after:
        last = await issue_resume(
            client,
            job_id=rj_id,
            after_message_id=rj_after,
            checkpoint_id=os.environ.get("RESUME_CHECKPOINT_ID"),
        )
        if last is None:
            print("already terminal during replay")
        else:
            next_idx = STEPS.index(last) + 1
            if next_idx >= len(STEPS):
                print("nothing to resume")
            else:
                print(f"[resuming at {STEPS[next_idx]}]")
                final = await execute_steps(
                    client,
                    job_id=rj_id,
                    request="<replayed>",
                    starting_at=STEPS[next_idx],
                    crash_after=None,
                )
                await client.send(
                    client.envelope(
                        "job.completed",
                        job_id=rj_id,
                        payload={"result": final},
                    )
                )
    else:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        request = "Survey CRDT-based collaborative editing in 2026."
        await client.send(
            client.envelope(
                "workflow.start",
                job_id=job_id,
                payload={
                    "workflow": "research.v1",
                    "arguments": {"request": request},
                },
            )
        )
        final = await execute_steps(
            client,
            job_id=job_id,
            request=request,
            starting_at=STEPS[0],
            crash_after=os.environ.get("CRASH_AFTER_STEP"),
        )
        await client.send(
            client.envelope(
                "job.completed",
                job_id=job_id,
                payload={"result": final},
            )
        )
        print(f"job_id={job_id}\n{final}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
