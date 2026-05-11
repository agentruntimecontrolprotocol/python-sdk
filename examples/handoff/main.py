"""Cheap-tier first; escalate to deep tier via agent.handoff."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import uuid

from arcp import ARCPClient, ARCPError, ErrorCode

from .cheap import attempt  # cheap-tier LLM call → (answer, confidence)

CONFIDENCE_THRESHOLD = 0.65
CHEAP_URL = "wss://haiku-pool.tier1.internal"
DEEP_URL = "wss://opus-pool.tier3.internal"
DEEP_KIND = "arcp-opus-pool"
DEEP_FINGERPRINT = "sha256:0a37bf7d61cca21f00..."  # pinned


async def package_context(
    client: ARCPClient, *, transcript: dict[str, object]
) -> dict[str, object]:
    body = json.dumps(transcript, sort_keys=True).encode()
    artifact_id = f"art_{uuid.uuid4().hex[:14]}"
    reply = await client.request(
        client.envelope(
            "artifact.put",
            payload={
                "artifact_id": artifact_id,
                "media_type": "application/json",
                "size": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "data": base64.b64encode(body).decode(),
            },
        ),
        timeout=15.0,
    )
    if reply.type != "artifact.ref":
        raise ARCPError(ErrorCode.INTERNAL, f"got {reply.type}")
    return reply.payload


async def emit_handoff(
    client: ARCPClient, *, artifact_ref: dict[str, object], trace_id: str
) -> None:
    await client.send(
        client.envelope(
            "agent.handoff",
            trace_id=trace_id,
            payload={
                "target_runtime": {
                    "url": DEEP_URL,
                    "kind": DEEP_KIND,
                    "fingerprint": DEEP_FINGERPRINT,
                },
                "session_id": client.session_id,
                # Spec gestures at shared_memory_ref (RFC §14); we use it
                # explicitly so the deep tier knows where the transcript lives.
                "shared_memory_ref": artifact_ref,
            },
        )
    )


async def main() -> None:
    cheap = ARCPClient(...)  # transport=WebSocketTransport(CHEAP_URL), pinned
    accepted = await cheap.open()
    # Pin runtime kind + fingerprint (RFC §8.3); refuse on mismatch.
    if accepted.runtime.kind != "arcp-haiku-pool":
        raise ARCPError(ErrorCode.UNAUTHENTICATED, "cheap kind mismatch")

    request = "what does CRDT stand for?"
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"

    answer, confidence = await attempt(request)
    if confidence >= CONFIDENCE_THRESHOLD:
        print(answer)
    else:
        artifact = await package_context(
            cheap,
            transcript={
                "user_request": request,
                "transcript": [
                    {"role": "user", "content": request},
                    {"role": "assistant", "content": answer},
                ],
                "cheap_confidence": confidence,
            },
        )
        await emit_handoff(cheap, artifact_ref=artifact, trace_id=trace_id)
        print(f"[handed off to {DEEP_KIND} trace_id={trace_id}]")

    await cheap.close()


if __name__ == "__main__":
    asyncio.run(main())
