"""§6.2 — `session.welcome` payload."""

from __future__ import annotations

from arcp._messages.session import (
    AgentInventoryEntry,
    Capabilities,
    RuntimeInfo,
    SessionWelcomePayload,
)


def test_welcome_minimum() -> None:
    p = SessionWelcomePayload(
        runtime=RuntimeInfo(name="r", version="1"),
        session_id="sess_x",
        resume_token="rtk_x",
        accepted_at="2026-05-14T12:00:00Z",
    )
    assert p.resume_window_sec == 600
    assert p.heartbeat_interval_sec is None


def test_welcome_with_rich_agents() -> None:
    p = SessionWelcomePayload(
        runtime=RuntimeInfo(name="r", version="1"),
        session_id="sess_x",
        resume_token="rtk_x",
        accepted_at="2026-05-14T12:00:00Z",
        capabilities=Capabilities(
            features=("agent_versions",),
            agents=(AgentInventoryEntry(name="a", versions=("1", "2"), default="2"),),
        ),
    )
    assert isinstance(p.capabilities.agents[0], AgentInventoryEntry)


def test_welcome_with_flat_agents() -> None:
    p = SessionWelcomePayload(
        runtime=RuntimeInfo(name="r", version="1"),
        session_id="sess_x",
        resume_token="rtk_x",
        accepted_at="2026-05-14T12:00:00Z",
        capabilities=Capabilities(features=(), agents=("agent1", "agent2")),
    )
    assert "agent1" in p.capabilities.agents
