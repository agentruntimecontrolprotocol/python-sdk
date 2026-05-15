"""Single-command entrypoint for the stdio example: just runs client.py."""

from __future__ import annotations

import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from client import main

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
