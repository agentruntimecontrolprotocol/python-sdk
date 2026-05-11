"""Cheap-tier inference. Real version: anthropic / litellm call with a
system prompt asking for a `Confidence: X.XX` line, then heuristics on
top to derive the final score."""

from __future__ import annotations


async def attempt(prompt: str) -> tuple[str, float]:
    raise NotImplementedError
