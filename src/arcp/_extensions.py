"""Extension key classifier for `x-vendor.*` and `arcpx.*` namespaces.

These extension-key namespaces are an SDK convention layered on the spec's
forward-compatibility rule (§5, ignore unknown fields); they are not defined
by a normative spec section.
"""

from __future__ import annotations


def is_vendor_extension(key: str) -> bool:
    """True if `key` is in the `x-vendor.<vendor>.*` namespace (SDK convention)."""
    return key.startswith("x-vendor.")


def is_reserved_extension(key: str) -> bool:
    """True if `key` is in the reserved `arcpx.*` namespace."""
    return key.startswith("arcpx.")


def validate_extension_key(key: str) -> None:
    """Reject extension keys that are neither vendor-namespaced nor reserved."""
    if not (is_vendor_extension(key) or is_reserved_extension(key)):
        raise ValueError(f"extension key must use x-vendor.* or arcpx.* namespace, got: {key!r}")


OTEL_EXTENSION_KEY: str = "x-vendor.opentelemetry.tracecontext"


__all__ = (
    "OTEL_EXTENSION_KEY",
    "is_reserved_extension",
    "is_vendor_extension",
    "validate_extension_key",
)
