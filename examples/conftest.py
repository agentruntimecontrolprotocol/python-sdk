"""Pytest config for `examples/`.

Adds `examples/` to ``sys.path`` so the per-example tests can import the
shared layer via ``from _shared.x import y`` regardless of whether pytest
is invoked from the repository root, from ``python-sdk/``, or from inside
``examples/`` itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))
