"""Fan a request out to peer runtimes; tolerate partial failure."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from arcp import ARCPClient, Envelope

from .synth import synthesize  # final LLM call

PEERS = ("research.web", "research.code", "research.docs")
_TERMINAL = frozenset({"job.completed", "job.failed", "job.cancelled"})


@dataclass(slots=True)
class Job:
    target: str
    job_id: str | None = None
    final: dict[str, object] | None = None
    error: dict[str, object] | None = None


async def delegate(
    client: ARCPClient, *, target: str, task: str, trace_id: str
) -> Job:
    accepted = await client.request(
        client.envelope(
            "agent.delegate",
            trace_id=trace_id,
            payload={
                "target": target,
                "task": task,
                # trace_id propagates so peers join one distributed trace.
                "context": {"trace_id": trace_id},
            },
        ),
        timeout=10.0,
    )
    if accepted.type != "job.accepted":
        return Job(
            target=target,
            error={
                "code": accepted.payload.get("code"),
                "message": accepted.payload.get("message"),
            },
        )
    return Job(target=target, job_id=str(accepted.payload["job_id"]))


class JobMux:
    """Single reader on `client.events()`; fans out by `job_id`.

    Without this, parallel `async for env in client.events():` loops
    starve each other — only one wins per await.
    """

    def __init__(self, client: ARCPClient) -> None:
        self._client = client
        self._queues: dict[str, asyncio.Queue[Envelope | None]] = {}
        self._reader: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._reader = asyncio.create_task(self._loop())

    def register(self, job_id: str) -> None:
        self._queues[job_id] = asyncio.Queue()

    async def stream(self, job: Job) -> AsyncIterator[Envelope]:
        if job.job_id is None:
            return
        q = self._queues[job.job_id]
        while (env := await q.get()) is not None:
            yield env
            if env.type in _TERMINAL:
                return

    async def _loop(self) -> None:
        async for env in self._client.events():
            if (jid := env.job_id) and jid in self._queues:
                await self._queues[jid].put(env)
                if env.type in _TERMINAL:
                    await self._queues[jid].put(None)


async def collect(mux: JobMux, job: Job) -> Job:
    if job.error is not None:
        return job
    async for env in mux.stream(job):
        if env.type == "job.completed":
            job.final = env.payload
        elif env.type == "job.failed":
            job.error = {
                "code": env.payload.get("code"),
                "message": env.payload.get("message"),
            }
        elif env.type == "job.cancelled":
            job.error = {"code": "CANCELLED", "message": "cancelled"}
    return job


async def main() -> None:
    client = ARCPClient(...)  # transport, identity, auth elided
    await client.open()

    mux = JobMux(client)
    mux.start()

    request = "what changed in our auth stack in the last 30 days?"
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"

    jobs = []
    for peer in PEERS:
        job = await delegate(
            client, target=peer, task=request, trace_id=trace_id
        )
        if job.job_id is not None:
            mux.register(job.job_id)
        jobs.append(job)

    completed = await asyncio.gather(*(collect(mux, j) for j in jobs))
    print(synthesize(request, list(completed)))

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
