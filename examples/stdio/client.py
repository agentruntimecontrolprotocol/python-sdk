"""stdio client — spawns server.py as a child process and talks NDJSON over its pipes."""

from __future__ import annotations

import asyncio
import contextlib
import os
import pathlib
import sys

from arcp import ClientInfo, StdioTransport
from arcp.client import ARCPClient

TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")
HERE = pathlib.Path(__file__).resolve().parent


async def main() -> int:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(HERE / "server.py"),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        # Forward stderr so server-side prints are visible.
        stderr=None,
    )
    async with contextlib.AsyncExitStack() as stack:
        # Ensure subprocess is reaped on every exit path.
        stack.push_async_callback(proc.wait)
        stack.callback(lambda: proc.kill() if proc.returncode is None else None)
        transport = await StdioTransport.from_process_pipes(proc)
        client = ARCPClient(
            client=ClientInfo(name="stdio-client", version="1.0.0"),
            token=TOKEN,
            features=(),
        )
        await stack.enter_async_context(contextlib.aclosing(client))
        await client.connect(transport)
        handle = await client.submit(agent="echo", input={"hello": "stdio"})
        async for ev in handle.events():
            print(f"[event] kind={ev['kind']}")
        result = await handle.done
        print(f"terminal: {result.final_status}")
        assert result.final_status == "success", result
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
