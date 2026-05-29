#!/usr/bin/env python3
"""Generate Markdown API docs for arcp.

For every Python module under ``src/arcp``, this script runs
``pydoc-markdown`` once and writes the rendered Markdown to
``docs/api/<dotted.module.path>.md`` -- one file per module. The site
at ``../www`` ingests ``python-sdk/docs/**/*.md`` at build time, so
the output deliberately stays as flat Markdown with no framework
trappings (no Hugo/Docusaurus front matter, no HTML).

Usage:
    python3 scripts/gen_api_docs.py

The shared loader/processor/renderer config lives in
``pydoc-markdown.yml`` next to this script's parent. We invoke
``pydoc-markdown <inline-yaml>`` per module so each invocation only
emits one module's documentation; that gives us one ``.md`` per
module without depending on the mkdocs/docusaurus multi-page
renderers, which would drag in framework-specific output.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "arcp"
OUT = ROOT / "docs" / "api"
CONFIG = ROOT / "pydoc-markdown.yml"


def discover_modules() -> list[str]:
    """Return every importable module under ``src/arcp`` as dotted paths."""
    modules: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC.parent)  # e.g. arcp/_client/client.py
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts or parts[-1] == "__main__":
            # Skip __main__ (entrypoint shim, no real API surface) and any
            # bare package root that collapsed to nothing.
            if parts and parts[-1] == "__main__":
                continue
            if not parts:
                continue
        modules.append(".".join(parts))
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for m in modules:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique


def render(module: str) -> str:
    """Run pydoc-markdown for a single module and return its Markdown."""
    # Inline YAML override: keep the shared config but pin `modules` to one
    # name. pydoc-markdown accepts a YAML string as the CONFIG arg.
    config_yaml = CONFIG.read_text(encoding="utf-8")
    # Append a `modules` entry to the python loader. The base config has
    # one loader with `search_path: [src]`; we add `modules: [...]` to it.
    override = config_yaml.replace(
        "    search_path: [src]",
        f"    search_path: [src]\n    modules: ['{module}']",
        1,
    )
    result = subprocess.run(
        ["pydoc-markdown", override],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def main() -> int:
    if shutil.which("pydoc-markdown") is None:
        print(
            "error: `pydoc-markdown` not on PATH. Install with "
            "`pipx install pydoc-markdown` and run `pipx inject "
            "pydoc-markdown <runtime deps>` so arcp is importable.",
            file=sys.stderr,
        )
        return 1

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)

    modules = discover_modules()
    if not modules:
        print("error: no modules discovered under src/arcp", file=sys.stderr)
        return 1

    print(f"Rendering {len(modules)} modules -> {OUT.relative_to(ROOT)}/")
    for module in modules:
        target = OUT / f"{module}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            markdown = render(module)
        except subprocess.CalledProcessError as exc:
            print(f"  FAIL  {module}", file=sys.stderr)
            print(exc.stderr, file=sys.stderr)
            return exc.returncode
        if not markdown.strip():
            print(f"  skip  {module} (empty)")
            continue
        target.write_text(markdown, encoding="utf-8")
        print(f"  ok    {module} -> {target.relative_to(ROOT)}")

    # Write an index so the site has a stable landing page for /api/.
    index = OUT / "README.md"
    lines = ["# Python SDK API reference", "", "Auto-generated from docstrings in `src/arcp`.", ""]
    for module in modules:
        md_path = f"{module}.md"
        lines.append(f"- [`{module}`]({md_path})")
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  ok    index -> {index.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
