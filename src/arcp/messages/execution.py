"""Execution payloads — tools, jobs, agents, workflows (RFC §10, §14)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

JobState = Literal[
    "accepted",
    "queued",
    "running",
    "blocked",
    "paused",
    "completed",
    "failed",
    "cancelled",
]


class ToolInvokePayload(BaseModel):
    """Direct tool invocation (§6.3)."""

    model_config = ConfigDict(extra="forbid")
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResultPayload(BaseModel):
    """``tool result`` payload."""

    model_config = ConfigDict(extra="forbid")
    value: Any | None = None
    result_ref: dict[str, Any] | None = None


class ToolErrorPayload(BaseModel):
    """Structured error from a tool (§18.1 in tool-shape)."""

    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    retryable: bool | None = None
    details: dict[str, Any] | None = None
    cause: dict[str, Any] | None = None
    trace_id: str | None = None


class JobAcceptedPayload(BaseModel):
    """``job accepted`` payload."""

    model_config = ConfigDict(extra="forbid")
    job_id: str
    state: JobState = "accepted"
    queued: bool = False


class JobStartedPayload(BaseModel):
    """``job started`` payload."""

    model_config = ConfigDict(extra="forbid")
    job_id: str


class JobProgressPayload(BaseModel):
    """``job progress`` payload."""

    model_config = ConfigDict(extra="forbid")
    percent: float | None = Field(default=None, ge=0, le=100)
    message: str | None = None


class JobHeartbeatPayload(BaseModel):
    """Liveness signal (§10.3)."""

    model_config = ConfigDict(extra="forbid")
    sequence: int = Field(ge=0)
    deadline_ms: int = Field(ge=0)
    state: JobState = "running"


class JobCheckpointPayload(BaseModel):
    """``job checkpoint`` payload."""

    model_config = ConfigDict(extra="forbid")
    checkpoint_id: str
    label: str | None = None


class JobCompletedPayload(BaseModel):
    """``job completed`` payload."""

    model_config = ConfigDict(extra="forbid")
    result: Any | None = None
    result_ref: dict[str, Any] | None = None


class JobFailedPayload(BaseModel):
    """``job failed`` payload."""

    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    retryable: bool | None = None
    details: dict[str, Any] | None = None


class JobCancelledPayload(BaseModel):
    """``job cancelled`` payload."""

    model_config = ConfigDict(extra="forbid")
    reason: str | None = None
    code: str = "CANCELLED"


class JobScheduleWhen(BaseModel):
    """Job schedule when."""

    model_config = ConfigDict(extra="forbid")
    at: str | None = None
    every: str | None = None
    after: int | None = Field(default=None, ge=0)


class JobSchedulePayload(BaseModel):
    """``job schedule`` payload."""

    model_config = ConfigDict(extra="forbid")
    job: dict[str, Any]
    when: JobScheduleWhen


class WorkflowStartPayload(BaseModel):
    """``workflow start`` payload."""

    model_config = ConfigDict(extra="forbid")
    workflow: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class WorkflowCompletePayload(BaseModel):
    """``workflow complete`` payload."""

    model_config = ConfigDict(extra="forbid")
    result: Any | None = None


class AgentDelegatePayload(BaseModel):
    """``agent delegate`` payload."""

    model_config = ConfigDict(extra="forbid")
    target: str
    task: str
    context: dict[str, Any] = Field(default_factory=dict)


class AgentHandoffPayload(BaseModel):
    """``agent handoff`` payload."""

    model_config = ConfigDict(extra="forbid")
    target_runtime: dict[str, Any]
    job_id: str | None = None
    session_id: str | None = None


PAYLOADS: dict[str, type[BaseModel]] = {
    "tool.invoke": ToolInvokePayload,
    "tool.result": ToolResultPayload,
    "tool.error": ToolErrorPayload,
    "job.accepted": JobAcceptedPayload,
    "job.started": JobStartedPayload,
    "job.progress": JobProgressPayload,
    "job.heartbeat": JobHeartbeatPayload,
    "job.checkpoint": JobCheckpointPayload,
    "job.completed": JobCompletedPayload,
    "job.failed": JobFailedPayload,
    "job.cancelled": JobCancelledPayload,
    "job.schedule": JobSchedulePayload,
    "workflow.start": WorkflowStartPayload,
    "workflow.complete": WorkflowCompletePayload,
    "agent.delegate": AgentDelegatePayload,
    "agent.handoff": AgentHandoffPayload,
}


__all__ = [
    "PAYLOADS",
    "AgentDelegatePayload",
    "AgentHandoffPayload",
    "JobAcceptedPayload",
    "JobCancelledPayload",
    "JobCheckpointPayload",
    "JobCompletedPayload",
    "JobFailedPayload",
    "JobHeartbeatPayload",
    "JobProgressPayload",
    "JobSchedulePayload",
    "JobScheduleWhen",
    "JobStartedPayload",
    "JobState",
    "ToolErrorPayload",
    "ToolInvokePayload",
    "ToolResultPayload",
    "WorkflowCompletePayload",
    "WorkflowStartPayload",
]
