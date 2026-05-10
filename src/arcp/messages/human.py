"""Human-in-the-loop payloads (RFC §12)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HumanInputRequestPayload(BaseModel):
    """Request structured input from a human (§12.1)."""

    model_config = ConfigDict(extra="forbid")
    prompt: str
    response_schema: dict[str, Any] = Field(default_factory=dict)
    default: Any | None = None
    expires_at: str
    context: dict[str, Any] | None = None


class HumanInputResponsePayload(BaseModel):
    """``human input response`` payload."""

    model_config = ConfigDict(extra="forbid")
    value: Any
    responded_by: str | None = None
    responded_at: str | None = None


class HumanChoiceOption(BaseModel):
    """Human choice option."""

    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    description: str | None = None


class HumanChoiceRequestPayload(BaseModel):
    """Request a multi-option choice (§12.2)."""

    model_config = ConfigDict(extra="forbid")
    prompt: str
    options: list[HumanChoiceOption]
    expires_at: str
    default_choice_id: str | None = None


class HumanChoiceResponsePayload(BaseModel):
    """``human choice response`` payload."""

    model_config = ConfigDict(extra="forbid")
    choice_id: str
    responded_by: str | None = None
    responded_at: str | None = None


class HumanInputCancelledPayload(BaseModel):
    """Notify other channels that the request resolved or expired (§12.3, §12.4)."""

    model_config = ConfigDict(extra="forbid")
    code: str
    reason: str | None = None


PAYLOADS: dict[str, type[BaseModel]] = {
    "human.input.request": HumanInputRequestPayload,
    "human.input.response": HumanInputResponsePayload,
    "human.choice.request": HumanChoiceRequestPayload,
    "human.choice.response": HumanChoiceResponsePayload,
    "human.input.cancelled": HumanInputCancelledPayload,
}


__all__ = [
    "PAYLOADS",
    "HumanChoiceOption",
    "HumanChoiceRequestPayload",
    "HumanChoiceResponsePayload",
    "HumanInputCancelledPayload",
    "HumanInputRequestPayload",
    "HumanInputResponsePayload",
]
