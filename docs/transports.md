# Transports

A **transport** is the communication channel between an `ARCPClient` and an `ARCPRuntime`. The SDK ships three transports out of the box. All implement the same `Transport` protocol, so you can swap them without changing application code.

## Transport protocol

```python
from typing import Any, Protocol


class Transport(Protocol):
    async def send(self, envelope: dict[str, Any]) -> None: ...
    async def recv(self) -> dict[str, Any]: ...
    async def close(self) -> None: ...

    @property
    def is_closed(self) -> bool: ...
```

`send` and `recv` exchange JSON-decoded envelope dicts; the SDK does its own framing.

## In-memory

The fastest option — no sockets, no serialisation overhead. Use it in tests and single-process demos.

```python
import asyncio
from arcp import ARCPClient, ClientInfo, pair_memory_transports

server_t, client_t = pair_memory_transports()

async def main() -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(runtime.accept(server_t))
        client = ARCPClient(client=ClientInfo(name="my-client", version="1.0.0"), token=TOKEN)
        await client.connect(client_t)

asyncio.run(main())
```

The two transports are connected: an envelope written to one is immediately readable from the other.

## WebSocket

For cross-process or cross-machine communication. The runtime exposes a WebSocket endpoint via `serve_websocket` (standalone) or `arcp_asgi_app` (mounted in an existing ASGI app); the client connects via `WebSocketTransport.connect`.

**Server (standalone, no framework):**

```python
from arcp._transport.websocket import serve_websocket

async def main() -> None:
    server = await serve_websocket(runtime.accept, host="127.0.0.1", port=7777, path="/arcp")
    async with server:
        await server.serve_forever()
```

**Server (ASGI):**

```python
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from arcp.middleware.asgi import arcp_asgi_app

app = Starlette(routes=[WebSocketRoute("/arcp", arcp_asgi_app(runtime))])
```

**Client:**

```python
from arcp import ARCPClient, ClientInfo, WebSocketTransport

client = ARCPClient(client=ClientInfo(name="my-client", version="1.0.0"), token=TOKEN)
transport = await WebSocketTransport.connect("ws://localhost:7777/arcp")
await client.connect(transport)
```

See the [host-asgi recipe](recipes/host-asgi.md) for a runnable server.

## stdio

For subprocess-based runtimes. The parent process spawns a child; the child reads from stdin and writes to stdout.

**Parent (client side):**

```python
import asyncio
from arcp import StdioTransport

proc = await asyncio.create_subprocess_exec(
    "python", "-m", "my_agent_server",
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
)
transport = await StdioTransport.from_process_pipes(proc)
await client.connect(transport)
```

**Child (server side)** — in `my_agent_server/__main__.py`:

```python
import asyncio
from arcp import StdioTransport

async def main() -> None:
    transport = await StdioTransport.from_std_streams()
    await runtime.accept(transport)

asyncio.run(main())
```

See the [stdio recipe](recipes/stdio.md) for the full pattern.

## Choosing a transport

| Transport | When to use |
|---|---|
| In-memory | Tests, benchmarks, single-process demos |
| WebSocket | Multi-process, cross-machine, browser clients |
| stdio | Subprocess agents, MCP-compatible tooling |

## Custom transports

Implement the four-member `Transport` protocol (`send`, `recv`, `close`, `is_closed`) to integrate with any I/O layer:

```python
from typing import Any


class MyTransport:
    def __init__(self) -> None:
        self._closed = False

    async def send(self, envelope: dict[str, Any]) -> None:
        await self._socket.send_json(envelope)

    async def recv(self) -> dict[str, Any]:
        return await self._socket.recv_json()

    async def close(self) -> None:
        self._closed = True
        await self._socket.close()

    @property
    def is_closed(self) -> bool:
        return self._closed
```

Pass it directly to `client.connect()` or `runtime.accept()`.
