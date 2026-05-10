"""Lease lifecycle management (RFC §15.5)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from arcp.errors import ARCPError, ErrorCode


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _format_iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class Lease:
    lease_id: str
    permission: str
    resource: str | None
    operation: str | None
    expires_at: datetime
    revoked: bool = False
    revoked_reason: str | None = None

    @property
    def is_expired(self) -> bool:
        return _now() >= self.expires_at

    @property
    def expires_at_iso(self) -> str:
        return _format_iso(self.expires_at)


@dataclass
class LeaseManager:
    """Per-session lease registry."""

    _leases: dict[str, Lease] = field(default_factory=dict[str, Lease])

    def grant(
        self,
        *,
        permission: str,
        resource: str | None,
        operation: str | None,
        seconds: int,
    ) -> Lease:
        lease = Lease(
            lease_id=f"lease_{uuid.uuid4().hex[:12]}",
            permission=permission,
            resource=resource,
            operation=operation,
            expires_at=_now() + timedelta(seconds=seconds),
        )
        self._leases[lease.lease_id] = lease
        return lease

    def get(self, lease_id: str) -> Lease:
        lease = self._leases.get(lease_id)
        if lease is None:
            raise ARCPError(ErrorCode.NOT_FOUND, f"lease {lease_id!r} not found")
        return lease

    def extend(self, lease_id: str, seconds: int) -> Lease:
        lease = self.get(lease_id)
        if lease.revoked:
            raise ARCPError(ErrorCode.LEASE_REVOKED, f"lease {lease_id!r} is revoked")
        if lease.is_expired:
            raise ARCPError(ErrorCode.LEASE_EXPIRED, f"lease {lease_id!r} is expired")
        lease.expires_at = _now() + timedelta(seconds=seconds)
        return lease

    def revoke(self, lease_id: str, reason: str | None = None) -> Lease:
        lease = self.get(lease_id)
        lease.revoked = True
        lease.revoked_reason = reason
        return lease

    def assert_valid(self, lease_id: str) -> Lease:
        lease = self.get(lease_id)
        if lease.revoked:
            raise ARCPError(ErrorCode.LEASE_REVOKED, f"lease {lease_id!r} is revoked")
        if lease.is_expired:
            raise ARCPError(ErrorCode.LEASE_EXPIRED, f"lease {lease_id!r} is expired")
        return lease


__all__ = ["Lease", "LeaseManager"]
