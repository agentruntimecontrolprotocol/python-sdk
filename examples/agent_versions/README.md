# agent_versions

Demonstrates spec §7.5 / §12: an agent with multiple versions, a server
default, and the rich `AgentInventoryEntry` shape that arrives in
`welcome.capabilities.agents` when `agent_versions` is negotiated. The
client submits three jobs: bare (default), pinned, and missing.

Advertised features: `("agent_versions",)`.

## Run

```sh
python examples/agent_versions/server.py    # terminal 1
python examples/agent_versions/client.py    # terminal 2
```

Client exits 0 when bare and `@1.2.3` succeed and `@9.9.9` raises
`AgentVersionNotAvailableError`.
