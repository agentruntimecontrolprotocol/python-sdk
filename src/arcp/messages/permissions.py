"""Permission and lease payloads (RFC §15)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PermissionRequestPayload(BaseModel):
    """Runtime asks the client for a permission grant (§15.4)."""

    model_config = ConfigDict(extra="forbid")
    permission: str
    resource: str | None = None
    operation: str | None = None
    reason: str | None = None
    requested_lease_seconds: int = Field(default=300, ge=1)


class PermissionGrantPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permission: str
    resource: str | None = None
    operation: str | None = None
    lease_seconds: int = Field(default=300, ge=1)


class PermissionDenyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permission: str
    reason: str | None = None
    code: str = "PERMISSION_DENIED"


class LeaseGrantedPayload(BaseModel):
    """Materialized lease emitted by the grantor (§15.5)."""

    model_config = ConfigDict(extra="forbid")
    lease_id: str
    permission: str
    resource: str | None = None
    operation: str | None = None
    expires_at: str
    granted_by: str | None = None


class LeaseExtendedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_id: str
    expires_at: str


class LeaseRevokedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_id: str
    reason: str | None = None
    code: str = "LEASE_REVOKED"


class LeaseRefreshPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_id: str
    extension_seconds: int = Field(default=300, ge=1)


PAYLOADS: dict[str, type[BaseModel]] = {
    "permission.request": PermissionRequestPayload,
    "permission.grant": PermissionGrantPayload,
    "permission.deny": PermissionDenyPayload,
    "lease.granted": LeaseGrantedPayload,
    "lease.extended": LeaseExtendedPayload,
    "lease.revoked": LeaseRevokedPayload,
    "lease.refresh": LeaseRefreshPayload,
}


__all__ = [
    "PAYLOADS",
    "LeaseExtendedPayload",
    "LeaseGrantedPayload",
    "LeaseRefreshPayload",
    "LeaseRevokedPayload",
    "PermissionDenyPayload",
    "PermissionGrantPayload",
    "PermissionRequestPayload",
]
