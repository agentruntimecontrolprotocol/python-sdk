"""ARCP command-line interface (Click)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from typing import Any

import click

from . import ClientInfo, Lease, WebSocketTransport
from ._envelope import Envelope
from ._runtime.server import ARCPRuntime, RuntimeInfo
from ._store.eventlog import EventLog, SqliteEventLog
from ._transport.websocket import serve_websocket
from .client import ARCPClient
from .runtime import StaticBearerVerifier


@click.group()
@click.version_option(prog_name="arcp")
def main() -> None:
    """ARCP reference CLI."""


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=7777, show_default=True, type=int)
@click.option("--token", required=True, help="Demo bearer token to accept.")
@click.option("--principal", default="cli-user", show_default=True)
@click.option("--db", default=None, help="Optional SQLite event log path.")
def serve(host: str, port: int, token: str, principal: str, db: str | None) -> None:
    """Run a minimal ARCP runtime serving the `echo` demo agent."""

    async def echo(input_value: Any, ctx: Any) -> Any:
        await ctx.log("info", "echo started")
        return {"echoed": input_value}

    log: EventLog | None = SqliteEventLog(db) if db else None
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="arcp-cli", version="1.1.0"),
        bearer=StaticBearerVerifier({token: principal}),
        event_log=log,
    )
    runtime.register_agent("echo", echo)

    async def go() -> None:
        server = await serve_websocket(runtime.accept, host=host, port=port, path="/arcp")
        click.echo(f"arcp serve listening on ws://{host}:{port}/arcp", err=True)
        async with server:
            await server.serve_forever()

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(go())


@main.command()
@click.option("--url", required=True, help="ws://host:port/arcp")
@click.option("--token", required=True)
@click.option("--agent", required=True)
@click.option("--input", "input_json", default="null")
@click.option(
    "--lease",
    default="{}",
    help='Lease as JSON object: {"net.fetch": ["https://*"]}',
)
def submit(url: str, token: str, agent: str, input_json: str, lease: str) -> None:
    """Submit a single job and print the terminal `job.result` JSON."""

    async def go() -> None:
        client = ARCPClient(client=ClientInfo(name="arcp-cli", version="1.1.0"), token=token)
        transport = await WebSocketTransport.connect(url)
        await client.connect(transport)
        try:
            lease_obj: Lease = json.loads(lease)
            handle = await client.submit(
                agent=agent, input=json.loads(input_json), lease_request=lease_obj
            )
            result = await handle.done
            click.echo(json.dumps(result.model_dump(mode="json", exclude_none=True), indent=2))
        finally:
            await client.close()

    asyncio.run(go())


@main.command()
@click.option("--url", required=True)
@click.option("--token", required=True)
@click.option("--job-id", required=True)
def tail(url: str, token: str, job_id: str) -> None:
    """Subscribe to `job_id` and stream events to stdout as JSON lines."""

    async def go() -> None:
        client = ARCPClient(client=ClientInfo(name="arcp-cli", version="1.1.0"), token=token)
        transport = await WebSocketTransport.connect(url)
        await client.connect(transport)
        try:
            sub = await client.subscribe(job_id, history=True)
            async for ev in sub.handle.events():
                click.echo(json.dumps(ev))
            result = await sub.handle.done
            click.echo(json.dumps(result.model_dump(mode="json", exclude_none=True)))
        finally:
            await client.close()

    asyncio.run(go())


@main.command()
@click.option("--db", required=True, help="SQLite event log path.")
@click.option("--session", required=True, help="Session id to replay.")
@click.option("--after-seq", default=0, type=int)
def replay(db: str, session: str, after_seq: int) -> None:
    """Replay envelopes from a SQLite event log to stdout."""

    async def go() -> None:
        log = SqliteEventLog(db)
        try:
            async for env_dict in log.read_since_seq(session, after_seq):
                env = Envelope.from_wire(env_dict)
                click.echo(json.dumps(env.to_wire()))
        finally:
            await log.close()

    asyncio.run(go())


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
