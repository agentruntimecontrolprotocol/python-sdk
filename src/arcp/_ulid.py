"""ULID minting for envelope, session, job, and result identifiers."""

from __future__ import annotations

from ulid import ULID


def new_ulid() -> str:
    """Return a new ULID string (Crockford base32, 26 chars)."""
    return str(ULID())


def new_envelope_id() -> str:
    """Mint an envelope id."""
    return new_ulid()


def new_session_id() -> str:
    """Mint a session id with the `sess_` prefix."""
    return f"sess_{new_ulid()}"


def new_job_id() -> str:
    """Mint a job id with the `job_` prefix."""
    return f"job_{new_ulid()}"


def new_result_id() -> str:
    """Mint a result id with the `res_` prefix."""
    return f"res_{new_ulid()}"


def new_resume_token() -> str:
    """Mint a resume token."""
    return f"rtk_{new_ulid()}"


__all__ = (
    "new_envelope_id",
    "new_job_id",
    "new_result_id",
    "new_resume_token",
    "new_session_id",
    "new_ulid",
)
