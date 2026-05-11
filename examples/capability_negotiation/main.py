"""Capability-driven peer routing with ordered fallback + cost rollup."""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from arcp import ARCPClient, ARCPError, Envelope, ErrorCode

PEERS = (
    "anthropic-haiku",
    "anthropic-sonnet",
    "openai-4o",
    "groq-llama",
)
FALLBACK_CHAINS: dict[str, tuple[str, ...]] = {
    "cheap_fast": ("groq-llama", "anthropic-haiku", "openai-4o"),
    "balanced": ("anthropic-sonnet", "openai-4o", "anthropic-haiku"),
    "deep": ("anthropic-sonnet",),
}
COST_CEILING_USD_PER_MTOK = 8.0
LATENCY_CEILING_MS = 800
RETRYABLE = frozenset(
    {
        ErrorCode.RESOURCE_EXHAUSTED,
        ErrorCode.UNAVAILABLE,
        ErrorCode.DEADLINE_EXCEEDED,
        ErrorCode.ABORTED,
    }
)


@dataclass(frozen=True, slots=True)
class Profile:
    cost_per_mtok: float
    p50_latency_ms: int
    model_class: str


def profile_from(caps) -> Profile:
    # Capabilities is `extra="allow"` so namespaced fields ride alongside
    # the core booleans. NOTE: §21 covers extension *messages* but not
    # extension *capability values* — load-bearing convention here.
    extra = caps.model_extra or {}
    return Profile(
        cost_per_mtok=float(extra.get("arcpx.market.cost_per_mtok.v1", 0.0)),
        p50_latency_ms=int(extra.get("arcpx.market.p50_latency_ms.v1", 0)),
        model_class=str(extra.get("arcpx.market.model_class.v1", "unknown")),
    )


def candidate_chain(
    profiles: dict[str, Profile], request_class: str
) -> list[str]:
    return [
        name
        for name in FALLBACK_CHAINS.get(request_class, ())
        if (p := profiles.get(name)) is not None
        and p.cost_per_mtok <= COST_CEILING_USD_PER_MTOK
        and p.p50_latency_ms <= LATENCY_CEILING_MS
    ]


async def invoke_with_fallback(
    *,
    clients: dict[str, ARCPClient],
    chain: list[str],
    tool: str,
    arguments: dict[str, object],
    trace_id: str,
) -> Envelope:
    """Walk the chain. Retryable error → next peer; otherwise raise."""
    last: ARCPError | None = None
    for name in chain:
        client = clients[name]
        try:
            reply = await client.request(
                client.envelope(
                    "tool.invoke",
                    trace_id=trace_id,
                    extensions={"arcpx.market.peer.v1": name},
                    payload={"tool": tool, "arguments": arguments},
                ),
                timeout=30.0,
            )
        except ARCPError as exc:
            last = exc
            if exc.code in RETRYABLE:
                continue
            raise
        if reply.type != "tool.error":
            return reply
        code = ErrorCode(reply.payload.get("code", "UNKNOWN"))
        last = ARCPError(code, str(reply.payload.get("message", "")))
        if code in RETRYABLE:
            continue
        raise last
    raise last or ARCPError(ErrorCode.UNAVAILABLE, "no peers available")


@dataclass(slots=True)
class Usage:
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    by_peer: dict[str, float] = field(default_factory=dict)


def consume_metric(env: Envelope, totals: dict[str, Usage]) -> None:
    if env.type != "metric":
        return
    p, dims = env.payload, env.payload.get("dims") or {}
    name, value = p.get("name"), p.get("value")
    if not isinstance(value, int | float):
        return
    u = totals[dims.get("tenant", "unknown")]
    if name == "tokens.used":
        kind = dims.get("kind")
        if kind == "input":
            u.tokens_in += int(value)
        elif kind == "output":
            u.tokens_out += int(value)
    elif name == "cost.usd":
        u.cost_usd += float(value)
        peer = dims.get("peer", "unknown")
        u.by_peer[peer] = u.by_peer.get(peer, 0.0) + float(value)


async def main() -> None:
    clients: dict[str, ARCPClient] = {}
    profiles: dict[str, Profile] = {}
    for name in PEERS:
        c = ARCPClient(...)  # transport per peer URL, identity, auth elided
        await c.open()
        clients[name] = c
        # Marketplace fields ride on the negotiated capabilities;
        # no extra round trip to learn cost / latency / class.
        profiles[name] = profile_from(c.negotiated_capabilities)

    totals: dict[str, Usage] = defaultdict(Usage)

    async def meter(c: ARCPClient) -> None:
        async for env in c.events():
            consume_metric(env, totals)

    drains = [asyncio.create_task(meter(c)) for c in clients.values()]

    chain = candidate_chain(profiles, "balanced")
    reply = await invoke_with_fallback(
        clients=clients,
        chain=chain,
        tool="chat.completion",
        arguments={"prompt": "Hello", "tenant": "acme-corp"},
        trace_id=f"trace_{uuid.uuid4().hex[:12]}",
    )
    print("chosen=", (reply.extensions or {}).get("arcpx.market.peer.v1"))
    print("usage=", dict(totals))

    for d in drains:
        d.cancel()
    for c in clients.values():
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
