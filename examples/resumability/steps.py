"""Step bodies. Real version: a LangGraph node per step (Anthropic
call for plan / synth / critique / finalize, LlamaIndex retriever
for gather)."""

from __future__ import annotations

from arcp import ARCPClient


async def run_step(
    client: ARCPClient,
    *,
    job_id: str,
    step: str,
    inputs: dict[str, object],
) -> object:
    raise NotImplementedError
