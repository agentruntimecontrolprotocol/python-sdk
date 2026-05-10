"""Artifact payloads (RFC §16)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ArtifactRefPayload(BaseModel):
    """Canonical pointer to an artifact (§16.1)."""

    model_config = ConfigDict(extra="forbid")
    artifact_id: str
    uri: str
    media_type: str
    size: int = Field(ge=0)
    sha256: str | None = None
    expires_at: str | None = None


class ArtifactPutPayload(BaseModel):
    """Upload an artifact inline as base64 (§16.2)."""

    model_config = ConfigDict(extra="forbid")
    media_type: str
    size: int = Field(ge=0)
    sha256: str | None = None
    expires_at: str | None = None
    data: str  # base64-encoded


class ArtifactFetchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_id: str
    inline: bool = True


class ArtifactReleasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_id: str


PAYLOADS: dict[str, type[BaseModel]] = {
    "artifact.put": ArtifactPutPayload,
    "artifact.fetch": ArtifactFetchPayload,
    "artifact.ref": ArtifactRefPayload,
    "artifact.release": ArtifactReleasePayload,
}


__all__ = [
    "PAYLOADS",
    "ArtifactFetchPayload",
    "ArtifactPutPayload",
    "ArtifactRefPayload",
    "ArtifactReleasePayload",
]
