"""Worker work. Real version: a CrewAI Crew sized per role, run via
crew.kickoff(inputs=...) inside an asyncio.to_thread."""

from __future__ import annotations


async def do_work(payload: dict[str, object]) -> dict[str, object]:
    raise NotImplementedError
