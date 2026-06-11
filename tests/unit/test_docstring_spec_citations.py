"""#76 — module docstrings must not cite spec subsections that do not exist."""

from __future__ import annotations

import inspect

from arcp import _envelope, _extensions
from arcp._transport import stdio

# ARCP v1.1 §5 (Wire Format) and §4 (Transport) have no subsections, and §15
# (IANA Considerations) does not define the extension-key namespaces.
_FORBIDDEN = ("§5.1", "§4.2")


def test_no_fabricated_subsection_citations() -> None:
    for module in (_envelope, stdio):
        src = inspect.getsource(module)
        for bad in _FORBIDDEN:
            assert bad not in src, f"{module.__name__} still cites {bad}"


def test_extension_namespace_no_longer_cites_section_15() -> None:
    src = inspect.getsource(_extensions)
    assert "§15" not in src
