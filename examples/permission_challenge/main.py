"""Generator proposes; reviewer holds veto via permission.request."""

from __future__ import annotations

import asyncio
import hashlib

from arcp import ARCPClient, ARCPError, Envelope, ErrorCode

from .agents import Patch, ReviewVerdict, propose, review

MAX_REVISIONS = 4


def fingerprint(diff: str) -> str:
    return hashlib.sha256(diff.encode()).hexdigest()[:16]


async def request_apply(
    client: ARCPClient, *, ticket_id: str, patch: Patch
) -> str:
    """Generator: ask for a `repo.write` lease scoped to this exact diff."""
    fp = fingerprint(patch.diff)
    reply = await client.request(
        client.envelope(
            "permission.request",
            # Same key per (ticket, diff): identical patch dedupes at runtime.
            idempotency_key=f"review:{ticket_id}:{fp}",
            payload={
                "permission": "repo.write",
                "resource": f"ticket:{ticket_id}/{fp}",
                "operation": "apply_patch",
                "reason": "apply patch",
                "requested_lease_seconds": 90,
            },
        ),
        timeout=300.0,
    )
    if reply.type == "permission.deny":
        raise ARCPError(
            ErrorCode.PERMISSION_DENIED,
            str(reply.payload.get("reason") or "denied"),
        )
    return str(reply.payload["lease_id"])


async def respond(
    client: ARCPClient,
    *,
    request: Envelope,
    verdict: ReviewVerdict,
) -> None:
    """Reviewer: grant or typed deny."""
    if verdict.grant:
        await client.send(
            client.envelope(
                "permission.grant",
                correlation_id=request.id,
                payload={
                    "permission": request.payload["permission"],
                    "resource": request.payload.get("resource"),
                    "operation": request.payload.get("operation"),
                    "lease_seconds": 90,
                },
            )
        )
    else:
        await client.send(
            client.envelope(
                "permission.deny",
                correlation_id=request.id,
                payload={
                    "permission": request.payload["permission"],
                    "reason": verdict.reason,
                    "code": str(ErrorCode.FAILED_PRECONDITION),
                },
            )
        )


async def reviewer_loop(reviewer: ARCPClient, ticket: str) -> None:
    async for env in reviewer.events():
        if env.type == "permission.request":
            verdict = await review(ticket=ticket, request=env)
            await respond(reviewer, request=env, verdict=verdict)


async def main() -> None:
    # Two sessions, one per agent. In production they'd be in different
    # processes on different runtimes; the message contract is identical.
    generator = ARCPClient(...)  # transport, identity, auth elided
    reviewer = ARCPClient(...)
    await generator.open()
    await reviewer.open()

    ticket_id = "JIRA-4812"
    ticket = (
        "Reject JWTs whose `aud` does not match the configured "
        "audience. Add a unit test."
    )
    rev_task = asyncio.create_task(reviewer_loop(reviewer, ticket))

    prior_denial: str | None = None
    try:
        for _ in range(MAX_REVISIONS):
            patch = await propose(ticket=ticket, prior_denial=prior_denial)
            try:
                lease = await request_apply(
                    generator, ticket_id=ticket_id, patch=patch
                )
            except ARCPError as exc:
                if exc.code != ErrorCode.PERMISSION_DENIED:
                    raise
                prior_denial = exc.message
                continue
            print(f"applied {fingerprint(patch.diff)} lease={lease}")
            return
        print("abandoned after max_revisions")
    finally:
        rev_task.cancel()
        await generator.close()
        await reviewer.close()


if __name__ == "__main__":
    asyncio.run(main())
