"""Stdout sink — production version uses structlog."""

from __future__ import annotations

from arcp import Envelope


class StdoutSink:
    async def handle(self, env: Envelope) -> None:
        # Real version: structlog.get_logger().info(env.type, **env.payload)
        ...
