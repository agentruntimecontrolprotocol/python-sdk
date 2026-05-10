"""Typed payload models and registry for ARCP message types (RFC §6.2).

Each submodule defines Pydantic models for the payload of one or more
message types. The :data:`PAYLOAD_MODELS` registry maps message-type strings
to their payload model so that a dispatcher can validate inbound payloads.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from arcp.messages import (
    artifacts,
    control,
    execution,
    human,
    permissions,
    streaming,
    subscriptions,
    telemetry,
)
from arcp.messages import (
    session as session_msgs,
)


def _collect() -> dict[str, type[BaseModel]]:
    registry: dict[str, type[BaseModel]] = {}
    for mod in (
        session_msgs,
        control,
        execution,
        streaming,
        human,
        permissions,
        subscriptions,
        artifacts,
        telemetry,
    ):
        registry.update(mod.PAYLOADS)
    return registry


PAYLOAD_MODELS: dict[str, type[BaseModel]] = _collect()


def validate_payload(message_type: str, payload: dict[str, Any]) -> BaseModel | None:
    """Validate ``payload`` against the registered model for ``message_type``.

    Returns the parsed model instance, or ``None`` if no model is registered
    for ``message_type`` (the dispatcher then falls back to extension/unknown
    handling per RFC §21.3).
    """
    model = PAYLOAD_MODELS.get(message_type)
    if model is None:
        return None
    return model.model_validate(payload)


__all__ = ["PAYLOAD_MODELS", "validate_payload"]
