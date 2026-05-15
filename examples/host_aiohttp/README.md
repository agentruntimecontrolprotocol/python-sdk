# host_aiohttp

`aiohttp.web` app serving an HTTP `/health` route alongside the ARCP
WebSocket upgrade at `/arcp` via `arcp.middleware.aiohttp.arcp_aiohttp_handler`.

```
python examples/host_aiohttp/server.py     # terminal 1
python examples/host_aiohttp/client.py     # terminal 2
```

Client success: `GET /health` returns `{"ok": true}`; submitted job
terminates `success`.
