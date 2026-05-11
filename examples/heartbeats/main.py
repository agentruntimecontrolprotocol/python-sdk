"""Supervisor + worker pool. Heartbeat loss reroutes via idempotency_key."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arcp import ARCPClient, Envelope

from .work import do_work  # CrewAI Crew or whatever does the actual job

HEARTBEAT_INTERVAL_SECONDS = 15
DEADLINE_S = HEARTBEAT_INTERVAL_SECONDS * 2  # RFC §10.3 default N=2


@dataclass(slots=True)
class Worker:
    worker_id: str
    role: str
    last_heartbeat: datetime
    in_flight_job: str | None = None


@dataclass(slots=True)
class Task:
    task_id: str
    role: str
    payload: dict[str, object]
    idempotency_key: str  # safety net for re-dispatch


@dataclass(slots=True)
class Roster:
    workers: dict[str, Worker] = field(default_factory=dict)
    by_role: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def add(self, w: Worker) -> None:
        self.workers[w.worker_id] = w
        self.by_role[w.role].append(w.worker_id)

    def candidates(self, role: str) -> list[Worker]:
        return [
            self.workers[wid]
            for wid in self.by_role.get(role, [])
            if self.workers[wid].in_flight_job is None
        ]


# Supervisor side --------------------------------------------------------


async def dispatch(
    client: ARCPClient,
    *,
    task: Task,
    roster: Roster,
    jobs_to_tasks: dict[str, Task],
) -> None:
    candidates = roster.candidates(task.role)
    if not candidates:
        raise RuntimeError(f"no idle workers for role={task.role}")
    worker = min(candidates, key=lambda w: w.last_heartbeat)
    # Same idempotency_key on every re-dispatch (RFC §6.4): a worker
    # that survived the network blip dedupes; it doesn't re-execute.
    accepted = await client.request(
        client.envelope(
            "agent.delegate",
            idempotency_key=task.idempotency_key,
            payload={
                "target": worker.worker_id,
                "task": task.task_id,
                "context": {"task_payload": task.payload},
            },
        ),
        timeout=10.0,
    )
    job_id = str(accepted.payload["job_id"])
    worker.in_flight_job = job_id
    jobs_to_tasks[job_id] = task


async def supervise(
    client: ARCPClient, roster: Roster, jobs_to_tasks: dict[str, Task]
) -> None:
    """Drain inbound + reap stale workers."""

    async def reaper() -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            now = datetime.now(tz=UTC).timestamp()
            for w in list(roster.workers.values()):
                if (now - w.last_heartbeat.timestamp()) <= DEADLINE_S:
                    continue
                jid = w.in_flight_job
                task = jobs_to_tasks.pop(jid, None) if jid else None
                if task is not None:
                    await dispatch(
                        client,
                        task=task,
                        roster=roster,
                        jobs_to_tasks=jobs_to_tasks,
                    )
                roster.workers.pop(w.worker_id, None)
                roster.by_role[w.role].remove(w.worker_id)

    asyncio.create_task(reaper())  # noqa: RUF006 — runs for main()'s lifetime

    async for env in client.events():
        if env.type == "job.heartbeat":
            for w in roster.workers.values():
                if w.in_flight_job == env.job_id:
                    w.last_heartbeat = datetime.now(tz=UTC)
        elif env.type in {"job.completed", "job.failed", "job.cancelled"}:
            jobs_to_tasks.pop(env.job_id or "", None)
            for w in roster.workers.values():
                if w.in_flight_job == env.job_id:
                    w.in_flight_job = None


# Worker side ------------------------------------------------------------


async def heartbeat_loop(
    client: ARCPClient, *, job_id: str, stop: asyncio.Event
) -> None:
    seq = 0
    while not stop.is_set():
        await client.send(
            client.envelope(
                "job.heartbeat",
                job_id=job_id,
                payload={
                    "sequence": seq,
                    "deadline_ms": HEARTBEAT_INTERVAL_SECONDS * 2000,
                    "state": "running",
                },
            )
        )
        seq += 1
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(
                stop.wait(), timeout=HEARTBEAT_INTERVAL_SECONDS
            )


async def execute(client: ARCPClient, env: Envelope) -> None:
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    await client.send(
        client.envelope(
            "job.accepted",
            job_id=job_id,
            correlation_id=env.id,
            payload={"job_id": job_id, "state": "accepted"},
        )
    )
    await client.send(
        client.envelope(
            "job.started",
            job_id=job_id,
            payload={"job_id": job_id},
        )
    )
    stop = asyncio.Event()
    hb = asyncio.create_task(heartbeat_loop(client, job_id=job_id, stop=stop))
    try:
        result = await do_work(
            env.payload.get("context", {}).get("task_payload", {})
        )
        await client.send(
            client.envelope(
                "job.completed",
                job_id=job_id,
                payload={"result": result},
            )
        )
    except Exception as exc:
        await client.send(
            client.envelope(
                "job.failed",
                job_id=job_id,
                payload={
                    "code": "INTERNAL",
                    "message": str(exc),
                    "retryable": True,
                },
            )
        )
    finally:
        stop.set()
        hb.cancel()


async def run_worker(client: ARCPClient) -> None:
    runners: set[asyncio.Task[None]] = set()
    async for env in client.events():
        if env.type == "agent.delegate":
            t = asyncio.create_task(execute(client, env))
            runners.add(t)
            t.add_done_callback(runners.discard)
        elif env.type == "session.evicted":
            return


async def main() -> None:
    supervisor = ARCPClient(
        ...
    )  # transport, identity (privileged), auth elided
    await supervisor.open()
    roster = Roster()
    jobs_to_tasks: dict[str, Task] = {}

    # In production each worker is its own process; co-hosted here for the demo.
    workers = []
    for role in ("indexer", "extractor", "archiver"):
        for _ in range(2):
            w = ARCPClient(...)  # worker session, capabilities advertise role
            await w.open()
            workers.append(asyncio.create_task(run_worker(w)))
            roster.add(
                Worker(
                    worker_id=f"{role}-{uuid.uuid4().hex[:6]}",
                    role=role,
                    last_heartbeat=datetime.now(tz=UTC),
                )
            )

    asyncio.create_task(  # noqa: RUF006
        supervise(supervisor, roster, jobs_to_tasks)
    )

    for n in range(6):
        await dispatch(
            supervisor,
            task=Task(
                task_id=f"t{n:03d}",
                role=("indexer", "extractor", "archiver")[n % 3],
                payload={"shard": n},
                idempotency_key=f"openclaw:t{n:03d}",
            ),
            roster=roster,
            jobs_to_tasks=jobs_to_tasks,
        )

    await asyncio.sleep(60)
    await supervisor.close()


if __name__ == "__main__":
    asyncio.run(main())
