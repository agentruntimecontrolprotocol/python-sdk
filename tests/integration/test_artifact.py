"""Artifact tests (RFC §16)."""

from __future__ import annotations

import asyncio
import base64

import pytest

from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.runtime.server import ARCPRuntime


@pytest.mark.asyncio
async def test_artifact_put_fetch_release(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, _, _ = connected
    accepted = await client.open()

    payload_bytes = b"hello, artifacts"
    encoded = base64.b64encode(payload_bytes).decode("ascii")

    put = Envelope(
        id="msg_put_1",
        type="artifact.put",
        session_id=accepted.session_id,
        payload={
            "media_type": "text/plain",
            "size": len(payload_bytes),
            "data": encoded,
        },
    )
    ref = await client.request(put, timeout=2.0)
    assert ref.type == "artifact.ref"
    artifact_id = ref.payload["artifact_id"]
    assert ref.payload["sha256"]

    fetch = Envelope(
        id="msg_fetch_1",
        type="artifact.fetch",
        session_id=accepted.session_id,
        payload={"artifact_id": artifact_id},
    )
    fetched = await client.request(fetch, timeout=2.0)
    assert fetched.type == "artifact.ref"
    assert base64.b64decode(fetched.payload["data"]) == payload_bytes

    release = Envelope(
        id="msg_release_1",
        type="artifact.release",
        session_id=accepted.session_id,
        payload={"artifact_id": artifact_id},
    )
    ack = await client.request(release, timeout=2.0)
    assert ack.type == "ack"

    fetch_again = Envelope(
        id="msg_fetch_2",
        type="artifact.fetch",
        session_id=accepted.session_id,
        payload={"artifact_id": artifact_id},
    )
    nack = await client.request(fetch_again, timeout=2.0)
    assert nack.type == "nack"
    assert nack.payload["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_artifact_put_rejects_bad_sha256(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, _, _ = connected
    accepted = await client.open()

    put = Envelope(
        id="msg_put_bad",
        type="artifact.put",
        session_id=accepted.session_id,
        payload={
            "media_type": "text/plain",
            "size": 5,
            "data": base64.b64encode(b"hello").decode("ascii"),
            "sha256": "0" * 64,
        },
    )
    nack = await client.request(put, timeout=2.0)
    assert nack.type == "nack"
    assert nack.payload["code"] == "INVALID_ARGUMENT"
