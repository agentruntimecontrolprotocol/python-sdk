"""Stand-in for the Anthropic tool-use loop. Real version: an
`anthropic.AsyncAnthropic` client with a system prompt, yielding one
LLMStep per turn."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolCall:
    argv: list[str]
    reason: str


@dataclass(frozen=True, slots=True)
class LLMStep:
    thought: str
    tool_call: ToolCall | None = None
    final: str | None = None


async def llm_loop(user_request: str) -> AsyncIterator[LLMStep]:
    raise NotImplementedError
