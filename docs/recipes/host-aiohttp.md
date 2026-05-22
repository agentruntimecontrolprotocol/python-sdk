# Host: aiohttp

Attaches `arcp.middleware.aiohttp.arcp_aiohttp_handler(runtime)` to an
`aiohttp.web.Application` route, serving ARCP from an aiohttp host
process.

Source: [`../../examples/host_aiohttp/`](../../examples/host_aiohttp/).

```sh
uv run python -m examples.host_aiohttp.server &
uv run python -m examples.host_aiohttp.client
```

## See also

- Guide: [Architecture](../architecture.md) — aiohttp middleware.
- Guide: [Transports](../transports.md).
