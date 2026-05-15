---
title: "arcp.middleware.aiohttp"
sdk: python
order: 7
kind: reference
---

Module `arcp.middleware.aiohttp`. Mounts an ARCP runtime as an
`aiohttp.web` WebSocket route.

## Symbols

| Name                    | Kind     | Summary                                                            |
| ----------------------- | -------- | ------------------------------------------------------------------ |
| `arcp_aiohttp_handler`  | function | Returns an aiohttp route handler bound to a given `ARCPRuntime`.   |
| `serve_arcp_aiohttp`    | function | Convenience: stand up an `aiohttp.web.AppRunner` on host / port.   |

## arcp_aiohttp_handler

```python
def arcp_aiohttp_handler(
    runtime: ARCPRuntime,
) -> Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.StreamResponse]]: ...
```

Attach to any `aiohttp.web.Application`:

```python
from aiohttp import web
from arcp.middleware.aiohttp import arcp_aiohttp_handler

app = web.Application()
app.router.add_get("/arcp", arcp_aiohttp_handler(runtime))
```

## serve_arcp_aiohttp

```python
async def serve_arcp_aiohttp(
    runtime: ARCPRuntime,
    *,
    host: str,
    port: int,
    path: str = "/arcp",
) -> aiohttp.web.AppRunner: ...
```

Stands up a complete aiohttp host serving only the ARCP route; the
returned runner is the caller's to clean up.

**Raises**: no exceptions surface to the aiohttp dispatcher; protocol
failures end the WebSocket with a `session.error` close frame.

## See also

- Example: [`../04-examples/host-aiohttp.md`](../04-examples/host-aiohttp.md).
- Reference: [`arcp-runtime.md`](arcp-runtime.md).
