"""Generator + reviewer stand-ins. Real version: AutoGen
AssistantAgents."""

from __future__ import annotations

from dataclasses import dataclass

from arcp import Envelope


@dataclass(frozen=True, slots=True)
class Patch:
    diff: str


@dataclass(frozen=True, slots=True)
class ReviewVerdict:
    grant: bool
    reason: str


async def propose(*, ticket: str, prior_denial: str | None) -> Patch:
    raise NotImplementedError


async def review(*, ticket: str, request: Envelope) -> ReviewVerdict:
    """Reviewer parses the patch out of `request.payload['resource']`
    or by looking it up by fingerprint, then runs the LLM."""
    raise NotImplementedError
