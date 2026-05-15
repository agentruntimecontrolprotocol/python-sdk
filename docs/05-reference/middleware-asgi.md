---
title: "arcp.middleware.asgi"
sdk: python
order: 6
kind: reference
---

Module `arcp.middleware.asgi`. Mounts an ARCP runtime as a WebSocket
ASGI sub-application; compatible with Starlette, FastAPI, Litestar,
and Quart.

## Symbols

| Name              | Kind     | Summary                                                              |
| ----------------- | -------- | -------------------------------------------------------------------- |
| `arcp_asgi_app`   | function | Returns an ASGI WebSocket handler bound to a given `ARCPRuntime`.    |

## arcp_asgi_app

```python
def arcp_asgi_app(
    runtime: ARCPRuntime,
    *,
    allowed_hosts: Sequence[str] | None = None,
) -> ASGIApp: ...
```

Returned callable matches the ASGI 3 signature
`(scope, receive, send)`. Mount at any path under your top-level app:

```python
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from arcp.middleware.asgi import arcp_asgi_app

app = Starlette(routes=[
    WebSocketRoute("/arcp", arcp_asgi_app(runtime, allowed_hosts=["app.example.com"])),
])
```

The handler validates the `Host` header against `allowed_hosts` (if
provided), upgrades the WebSocket, wraps it as a `Transport`, and
hands it to `runtime.accept`.

**Raises**: no exceptions surface to ASGI; protocol failures end the
WebSocket with a `session.error` close frame.

## See also

- Example: [`../04-examples/host-asgi.md`](../04-examples/host-asgi.md).
- Reference: [`arcp-runtime.md`](arcp-runtime.md).
