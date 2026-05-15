# host_asgi

Starlette ASGI app serving an HTTP `/health` route alongside the ARCP
WebSocket upgrade at `/arcp` via `arcp.middleware.asgi.arcp_asgi_app`.

```
python examples/host_asgi/server.py     # terminal 1
python examples/host_asgi/client.py     # terminal 2
```

Client success: `GET /health` returns `{"ok": true, ...}`; submitted job
terminates `success`. Demonstrates that the SDK's WS handler co-mounts
cleanly inside an existing ASGI app.
