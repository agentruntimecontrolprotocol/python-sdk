"""End-to-end test over a stdio (in-process StreamReader/Writer pair)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from arcp.auth.bearer import StaticTokenValidator
from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.messages.session import AuthBlock, Capabilities, Identity, RuntimeIdentity
from arcp.runtime.job import JobContext
from arcp.runtime.server import ARCPRuntime, RuntimeConfig
from arcp.transport.stdio import StdioTransport
from tests.integration.conftest import default_advertised


def make_stdio_pipe_pair() -> tuple[StdioTransport, StdioTransport]:
    """Create two StdioTransport endpoints connected by in-memory pipes."""

    loop = asyncio.get_running_loop()

    a_to_b_reader = asyncio.StreamReader()
    a_to_b_protocol = asyncio.StreamReaderProtocol(a_to_b_reader)
    b_to_a_reader = asyncio.StreamReader()
    b_to_a_protocol = asyncio.StreamReaderProtocol(b_to_a_reader)

    class _PipeTransport(asyncio.Transport):
        def __init__(self, target: asyncio.StreamReader) -> None:
            super().__init__()
            self._target = target
            self._closed = False

        def write(self, data: bytes | bytearray | memoryview[Any]) -> None:
            if not self._closed:
                self._target.feed_data(bytes(data))

        def is_closing(self) -> bool:
            return self._closed

        def close(self) -> None:
            if self._closed:
                return
            self._closed = True
            self._target.feed_eof()

        def can_write_eof(self) -> bool:
            return True

        def write_eof(self) -> None:
            self.close()

    a_writer_transport = _PipeTransport(a_to_b_reader)
    b_writer_transport = _PipeTransport(b_to_a_reader)

    a_writer = asyncio.StreamWriter(a_writer_transport, a_to_b_protocol, None, loop)
    b_writer = asyncio.StreamWriter(b_writer_transport, b_to_a_protocol, None, loop)

    a = StdioTransport(b_to_a_reader, a_writer)
    b = StdioTransport(a_to_b_reader, b_writer)
    return a, b


@pytest.mark.asyncio
async def test_stdio_full_lifecycle() -> None:
    rt = ARCPRuntime(
        config=RuntimeConfig(
            runtime_identity=RuntimeIdentity(kind="rt", version="1"),
            advertised_capabilities=default_advertised(),
            bearer_validator=StaticTokenValidator({"good": "alice"}),
        )
    )
    await rt.start()

    async def echo(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        return {"echo": args}

    rt.register_tool("echo", echo)

    client_t, server_t = make_stdio_pipe_pair()
    server_task = asyncio.create_task(rt.serve_session(server_t))

    client = ARCPClient(
        transport=client_t,
        client_identity=Identity(kind="t", version="1"),
        auth=AuthBlock(scheme="bearer", token="good"),
        capabilities=Capabilities(streaming=True, human_input=True, artifacts=True, subscriptions=True),
    )
    try:
        accepted = await client.open()
        invoke = Envelope(
            id="msg_inv_stdio",
            type="tool.invoke",
            session_id=accepted.session_id,
            payload={"tool": "echo", "arguments": {"x": 2}},
        )
        await client.send(invoke)

        async def _wait_for_completion() -> Envelope:
            async for env in client.events():
                if env.type == "job.completed":
                    return env
            raise AssertionError("no job.completed")

        completion = await asyncio.wait_for(_wait_for_completion(), timeout=3.0)
        assert completion.payload["result"] == {"echo": {"x": 2}}
    finally:
        await client.close()
        server_task.cancel()
        try:
            await server_task
        except BaseException:
            pass
        await rt.close()
