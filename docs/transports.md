# Transports

A **transport** is the communication channel between an `ARCPClient` and an `ARCPRuntime`. The SDK ships three transports out of the box. All implement the same `Transport` protocol, so you can swap them without changing application code.

## Transport protocol

```python
from arcp import Transport  # typing.Protocol

class Transport(Protocol):
    async def send(self, message: bytes) -> None: ...
    async def recv(self) -> bytes: ...
    async def close(self) -> None: ...
```

## In-memory

The fastest option — no sockets, no serialisation overhead. Use it in tests and single-process demos.

```python
from arcp import pair_memory_transports

client_t, server_t = pair_memory_transports()

async with asyncio.TaskGroup() as tg:
    tg.create_task(runtime.accept(server_t))
    await client.connect(client_t)
```

The two transports are connected: data written to one is immediately readable from the other.

## WebSocket

For cross-process or cross-machine communication. The runtime exposes a WebSocket endpoint; the client connects to it.

**Server** (FastAPI example):

```python
from fastapi import FastAPI
from arcp.middleware.asgi import ARCPMiddleware

app = FastAPI()
app.add_middleware(ARCPMiddleware, runtime=runtime)
# Mounts WebSocket at ws://host/arcp
```

**Client**:

```python
from arcp import ARCPClient, ClientInfo
from arcp.transport import WebSocketClientTransport

client = ARCPClient(client=ClientInfo(name="my-client", version="1.0.0"), token=TOKEN)
await client.connect(WebSocketClientTransport("ws://localhost:8000/arcp"))
```

See the [host-asgi recipe](recipes/host-asgi.md) for a runnable server.

## stdio

For subprocess-based runtimes. The parent process spawns a child; the child reads from stdin and writes to stdout.

**Parent (client side)**:

```python
from arcp.transport import StdioClientTransport

transport = await StdioClientTransport.spawn(["python", "-m", "my_agent_server"])
await client.connect(transport)
```

**Child (server side)** — in `my_agent_server/__main__.py`:

```python
from arcp.transport import StdioServerTransport

async def main():
    transport = StdioServerTransport()
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

Implement the three-method `Transport` protocol to integrate with any I/O layer:

```python
class MyTransport:
    async def send(self, message: bytes) -> None:
        await self._socket.write(message)

    async def recv(self) -> bytes:
        return await self._socket.read()

    async def close(self) -> None:
        await self._socket.close()
```

Pass it directly to `client.connect()` or `runtime.accept()`.
