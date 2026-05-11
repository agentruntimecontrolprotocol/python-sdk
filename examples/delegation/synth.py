"""Final-pass synthesizer. Real version: an Anthropic call that
folds successful subagent outputs into prose, ignoring failed
peers."""

from __future__ import annotations


def synthesize(request: str, jobs: list) -> str:
    raise NotImplementedError
