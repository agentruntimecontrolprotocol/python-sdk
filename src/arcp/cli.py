"""ARCP command-line interface.

Subcommands:

* ``arcp serve --transport ws --bind localhost:7777`` — start a runtime that
  echoes any registered tool. v0.1 ships only the ``echo`` tool out of the box.
* ``arcp send --type ping`` — send a single envelope to a running runtime
  (over WebSocket) and print the response.
* ``arcp tail --session sess_xxx`` — open a passive subscription against a
  running runtime and print every event matching the filter.
* ``arcp replay --session sess_xxx --after msg_xxx`` — replay events from
  the local SQLite event log file (offline).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import click
import structlog

from arcp.auth.bearer import StaticTokenValidator
from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.messages.session import (
    AuthBlock,
    Capabilities,
    Identity,
    RuntimeIdentity,
)
from arcp.runtime.job import JobContext
from arcp.runtime.server import ARCPRuntime, RuntimeConfig
from arcp.store.eventlog import EventLog
from arcp.transport.websocket import (
    ServerConnection,
    WebSocketTransport,
    connect_websocket,
    ws_serve,
)

logger = structlog.get_logger("arcp.cli")


@click.group()
def main() -> None:
    """ARCP reference CLI."""


def _default_caps() -> Capabilities:
    return Capabilities(
        streaming=True,
        durable_jobs=True,
        binary_streams=True,
        binary_encoding=["base64"],
        human_input=True,
        artifacts=True,
        subscriptions=True,
        interrupt=True,
        anonymous=True,
        heartbeat_interval_seconds=30,
        heartbeat_recovery="fail",
    )


@main.command()
@click.option("--transport", type=click.Choice(["ws"]), default="ws")
@click.option("--bind", default="127.0.0.1:7777")
@click.option("--token", multiple=True, help="bearer token in the form 'token=principal'.")
def serve(transport: str, bind: str, token: tuple[str, ...]) -> None:
    """Start an ARCP runtime listening on ``--bind``."""
    host, _, port_s = bind.rpartition(":")
    port = int(port_s)
    if not host:
        host = "127.0.0.1"

    tokens: dict[str, str] = {}
    for entry in token:
        key, _, principal = entry.partition("=")
        tokens[key] = principal or "anonymous"

    rt = ARCPRuntime(
        config=RuntimeConfig(
            runtime_identity=RuntimeIdentity(kind="arcp-py", version="0.1.0"),
            advertised_capabilities=_default_caps(),
            bearer_validator=StaticTokenValidator(tokens) if tokens else None,
        )
    )

    async def _echo(_ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        return {"echo": args}

    rt.register_tool("echo", _echo)

    async def _run() -> None:
        await rt.start()
        click.echo(f"arcp runtime listening on {transport}://{host}:{port}")

        async def _handler(ws: ServerConnection) -> None:
            await rt.serve_session(WebSocketTransport(ws))

        async with ws_serve(_handler, host, port) as server:
            await server.serve_forever()

    asyncio.run(_run())


@main.command()
@click.option("--uri", default="ws://127.0.0.1:7777")
@click.option("--type", "msg_type", required=True, help="envelope type, e.g. 'ping'.")
@click.option(
    "--payload",
    default="{}",
    help="JSON object payload. Defaults to empty.",
)
@click.option("--token", default=None)
def send(uri: str, msg_type: str, payload: str, token: str | None) -> None:
    """Send a single envelope of ``--type`` and print the first correlated reply."""
    parsed_payload: dict[str, Any] = json.loads(payload)

    async def _run() -> None:
        transport = await connect_websocket(uri)
        client = ARCPClient(
            transport=transport,
            client_identity=Identity(kind="arcp-cli", version="0.1.0"),
            auth=AuthBlock(scheme="bearer", token=token) if token else AuthBlock(scheme="none"),
            capabilities=Capabilities(anonymous=True),
        )
        accepted = await client.open()
        env = Envelope(
            id=f"msg_{msg_type}_send",
            type=msg_type,
            session_id=accepted.session_id,
            payload=parsed_payload,
        )
        try:
            response = await client.request(env, timeout=5.0)
            click.echo(json.dumps(response.to_wire(), indent=2))
        finally:
            await client.close()

    asyncio.run(_run())


@main.command()
@click.option("--db", required=True, help="path to a SQLite event log file")
@click.option("--session", "session_id", required=True)
@click.option("--after", "after_message_id", default=None)
def replay(db: str, session_id: str, after_message_id: str | None) -> None:
    """Offline replay of events from a saved event-log database."""

    async def _run() -> None:
        log = EventLog(Path(db))
        await log.open()
        try:
            async for env in log.replay(session_id=session_id, after_message_id=after_message_id):
                click.echo(json.dumps(env.to_wire()))
        finally:
            await log.close()

    asyncio.run(_run())


@main.command()
@click.option("--uri", default="ws://127.0.0.1:7777")
@click.option("--token", default=None)
@click.option("--types", default=None, help="comma-separated event types to filter")
def tail(uri: str, token: str | None, types: str | None) -> None:
    """Open a subscription against a running runtime and stream events."""

    async def _run() -> None:
        transport = await connect_websocket(uri)
        client = ARCPClient(
            transport=transport,
            client_identity=Identity(kind="arcp-cli-tail", version="0.1.0"),
            auth=AuthBlock(scheme="bearer", token=token) if token else AuthBlock(scheme="none"),
            capabilities=Capabilities(anonymous=True, subscriptions=True),
        )
        accepted = await client.open()
        filt: dict[str, Any] = {}
        if types is not None:
            filt["types"] = [t.strip() for t in types.split(",") if t.strip()]
        sub = Envelope(
            id="msg_tail_sub",
            type="subscribe",
            session_id=accepted.session_id,
            payload={"filter": filt},
        )
        await client.request(sub, timeout=5.0)
        try:
            async for env in client.events():
                click.echo(json.dumps(env.to_wire()))
        finally:
            await client.close()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
