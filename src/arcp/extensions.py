"""Extension registry and unknown-message handling (RFC §21).

Extensions are namespaced message types or fields outside the core surface. This
module enforces the naming rules in §21.1 and implements the unknown-message
classification rules in §21.3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from arcp.envelope import Envelope
from arcp.errors import ARCPError, ErrorCode

# RFC §21.1: extension names use either ``arcpx.<vendor-or-domain>.<name>.v<n>``
# or a reverse-DNS prefix such as ``com.acme.workflow.v2``. The bare ``x-`` prefix
# is reserved for transport-internal experimental fields and is rejected here.
_ARCPX_PATTERN = re.compile(r"^arcpx(\.[a-z][a-z0-9_-]*)+\.v\d+$")
_REVERSE_DNS_PATTERN = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9_-]*)+\.v\d+$")

# Recognized core message-type prefixes per §6.2. A type matching one of these
# prefixes but not present in the message registry is unknown-core, and §21.3
# requires ``UNIMPLEMENTED``.
CORE_PREFIXES: frozenset[str] = frozenset(
    {
        "session.",
        "job.",
        "tool.",
        "stream.",
        "human.",
        "permission.",
        "lease.",
        "subscribe",  # subscribe / subscribe.* / subscription.*
        "subscription.",
        "artifact.",
        "event.",
        "trace.",
        "checkpoint.",
        "agent.",
        "workflow.",
    }
)

# Standalone (no dot) core message types per §6.2.
CORE_STANDALONE: frozenset[str] = frozenset(
    {
        "ping",
        "pong",
        "ack",
        "nack",
        "cancel",
        "interrupt",
        "resume",
        "backpressure",
        "log",
        "metric",
    }
)


def is_extension_name(message_type: str) -> bool:
    """Return ``True`` if ``message_type`` matches a recognized extension namespace."""

    if message_type.startswith("x-"):
        return False
    return bool(_ARCPX_PATTERN.match(message_type) or _REVERSE_DNS_PATTERN.match(message_type))


def validate_extension_name(message_type: str) -> None:
    """Validate ``message_type`` as an extension name; raise on rejection.

    Raises :class:`ARCPError` with ``INVALID_ARGUMENT`` when the name does not
    conform to §21.1 (``arcpx.*.v<n>`` or reverse-DNS ``*.v<n>``), or when a
    bare ``x-`` prefix is used in a context where it is forbidden.
    """

    if message_type.startswith("x-"):
        raise ARCPError(
            ErrorCode.INVALID_ARGUMENT,
            f"Extension name {message_type!r} uses reserved 'x-' prefix",
        )
    if not is_extension_name(message_type):
        raise ARCPError(
            ErrorCode.INVALID_ARGUMENT,
            f"Extension name {message_type!r} does not match arcpx.*.v<n> or reverse-DNS form",
        )


def is_core_type(message_type: str) -> bool:
    """Return ``True`` if ``message_type`` belongs to a core RFC §6.2 prefix."""

    if message_type in CORE_STANDALONE:
        return True
    return any(message_type.startswith(prefix) for prefix in CORE_PREFIXES)


@dataclass
class ExtensionRegistry:
    """Tracks negotiated extension namespaces for a session (RFC §21.2)."""

    advertised: set[str] = field(default_factory=set[str])

    def advertise(self, name: str) -> None:
        """Register ``name`` as advertised. Validates the namespace shape."""

        validate_extension_name(name)
        self.advertised.add(name)

    def is_advertised(self, message_type: str) -> bool:
        """Return ``True`` iff ``message_type`` is covered by an advertised namespace.

        A namespace ``arcpx.acme.foo.v1`` covers messages whose name begins with
        ``arcpx.acme.foo.``; the version suffix on the namespace acts as a
        bounding tag rather than a strict equality check.
        """

        for ns in self.advertised:
            if message_type == ns or message_type.startswith(ns.rsplit(".v", 1)[0] + "."):
                return True
        return False


@dataclass
class UnknownMessageDecision:
    """Outcome of dispatching an unknown message type per RFC §21.3."""

    action: str  # "drop" | "nack"
    reason: str


def classify_unknown(envelope: Envelope, registry: ExtensionRegistry) -> UnknownMessageDecision:
    """Classify an unknown-type envelope per §21.3.

    Returns ``("drop", reason)`` when the receiver should silently drop (and log
    at debug level); returns ``("nack", reason)`` when the receiver should
    respond with ``nack`` and ``code: UNIMPLEMENTED``.
    """

    msg_type = envelope.type
    if is_core_type(msg_type):
        return UnknownMessageDecision(action="nack", reason=f"unknown core type {msg_type!r}")

    if not is_extension_name(msg_type):
        return UnknownMessageDecision(
            action="nack",
            reason=f"type {msg_type!r} is neither core nor a recognized extension",
        )

    if registry.is_advertised(msg_type):
        # Advertised but not registered handler-side: treat as missing implementation.
        return UnknownMessageDecision(
            action="nack",
            reason=f"advertised extension {msg_type!r} has no registered handler",
        )

    optional = bool((envelope.extensions or {}).get("optional", False))
    if optional:
        return UnknownMessageDecision(
            action="drop", reason=f"optional unadvertised extension {msg_type!r}"
        )

    return UnknownMessageDecision(
        action="nack", reason=f"non-optional unadvertised extension {msg_type!r}"
    )


__all__ = [
    "CORE_PREFIXES",
    "CORE_STANDALONE",
    "ExtensionRegistry",
    "UnknownMessageDecision",
    "classify_unknown",
    "is_core_type",
    "is_extension_name",
    "validate_extension_name",
]
