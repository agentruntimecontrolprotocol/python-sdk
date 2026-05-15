---
title: "arcp.transport"
sdk: python
order: 3
kind: reference
---

Module `arcp` re-exports the transport surface from
`arcp._transport`. A `Transport` is a duplex JSON envelope channel;
both sides use the same protocol regardless of carrier.

## Symbols

| Name                     | Kind     | Summary                                              |
| ------------------------ | -------- | ---------------------------------------------------- |
| `Transport`              | proto    | Async `send` / `recv` / `close` / `is_closed`.       |
| `TransportClosed`        | class    | Raised by `recv` when the peer closes.               |
| `MemoryTransport`        | class    | In-process duplex queue.                             |
| `pair_memory_transports` | function | Returns a connected `(client, server)` pair.         |
| `WebSocketTransport`     | class    | Wraps a `websockets` connection.                     |
| `StdioTransport`         | class    | Newline-delimited JSON over child-process pipes.     |
| `serve_websocket`        | function | Helper that runs an ARCP runtime on `ws://host:port/path`. |

## Transport

```python
class Transport(Protocol):
    async def send(self, envelope: dict[str, Any]) -> None: ...
    async def recv(self) -> dict[str, Any]: ...
    async def close(self) -> None: ...
    @property
    def is_closed(self) -> bool: ...
```

Envelopes are dictionaries on the wire (after `Envelope.to_wire()`)
and dictionaries off the wire (before `Envelope.from_wire(...)`).

**Raises**: `recv` raises `TransportClosed` when the peer ends the
session.

## pair_memory_transports

```python
def pair_memory_transports() -> tuple[MemoryTransport, MemoryTransport]: ...
```

Returns two connected transports; `send` on one yields to `recv` on
the other. Use for in-process tests and single-process examples.

## WebSocketTransport

```python
class WebSocketTransport:
    @classmethod
    async def connect(cls, url: str, **kwargs: Any) -> WebSocketTransport: ...
```

Client-side connect uses `websockets.connect`; runtime-side wrapping
happens inside `serve_websocket(handler, host, port, path)`.

## StdioTransport

```python
class StdioTransport:
    @classmethod
    async def from_process_pipes(cls, stdin_writer, stdout_reader) -> StdioTransport: ...
    @classmethod
    async def from_std_streams(cls) -> StdioTransport: ...
```

`from_std_streams` is the child-process entry; `from_process_pipes`
is the parent-side wrapper around an asyncio subprocess.

## serve_websocket

```python
async def serve_websocket(
    on_connect: Callable[[Transport], Awaitable[None]],
    *,
    host: str,
    port: int,
    path: str = "/arcp",
) -> websockets.server.Server: ...
```

Returns an awaitable server object; await `server.serve_forever()` to
run.

## See also

- Example: [`../04-examples/stdio.md`](../04-examples/stdio.md).
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §4.
