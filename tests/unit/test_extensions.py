"""Unit tests for arcp._extensions (spec §15 extension-key namespace rules)."""

from __future__ import annotations

import pytest

from arcp._extensions import (
    OTEL_EXTENSION_KEY,
    is_reserved_extension,
    is_vendor_extension,
    validate_extension_key,
)


def test_is_vendor_extension_true() -> None:
    assert is_vendor_extension("x-vendor.opentelemetry.tracecontext") is True
    assert is_vendor_extension("x-vendor.acme.debug") is True


def test_is_vendor_extension_false() -> None:
    assert is_vendor_extension("arcpx.foo") is False
    assert is_vendor_extension("x-custom.bar") is False
    assert is_vendor_extension("foo") is False


def test_is_reserved_extension_true() -> None:
    assert is_reserved_extension("arcpx.sampling") is True
    assert is_reserved_extension("arcpx.foo.bar") is True


def test_is_reserved_extension_false() -> None:
    assert is_reserved_extension("x-vendor.foo") is False
    assert is_reserved_extension("custom") is False


def test_validate_extension_key_vendor_ok() -> None:
    validate_extension_key("x-vendor.acme.trace")  # must not raise


def test_validate_extension_key_reserved_ok() -> None:
    validate_extension_key("arcpx.experiment")  # must not raise


def test_validate_extension_key_invalid() -> None:
    with pytest.raises(ValueError, match=r"x-vendor.*arcpx"):
        validate_extension_key("custom.key")


def test_otel_extension_key_constant() -> None:
    assert OTEL_EXTENSION_KEY == "x-vendor.opentelemetry.tracecontext"
    assert is_vendor_extension(OTEL_EXTENSION_KEY)
