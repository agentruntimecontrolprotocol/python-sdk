"""Primary + critic LLM stand-ins."""

from __future__ import annotations

from typing import Literal


async def primary_step(
    request: str, prior_critique: dict[str, object] | None
) -> str:
    """One reasoning step. Real version: an Anthropic call that
    folds the critique into the prompt when present."""
    raise NotImplementedError


async def critique_thought(
    thought: str,
) -> tuple[Literal["nudge", "warn", "halt"], str, str | None, int]:
    """Critic LLM. Returns (severity, summary, suggestion, tokens_consumed)."""
    raise NotImplementedError
