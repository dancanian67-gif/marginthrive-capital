"""One-time helper to split app.py into Phase C1 modules. Run from project root."""
from __future__ import annotations

import pathlib
import re
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
SOURCE = APP.read_text(encoding="utf-8")
LINES = SOURCE.splitlines(keepends=True)


def slice_lines(start: int, end: int) -> str:
    return "".join(LINES[start - 1 : end])


def write(path: str, header: str, body: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    content = header.rstrip() + "\n\n" + body.strip() + "\n"
    target.write_text(content, encoding="utf-8")
    print(f"wrote {path}")


# Extract function/class blocks by line numbers from current app.py (1-indexed)
WORKFLOW_START = 1957  # _normalize_sub_status through _apply_workflow_quick_action
WORKFLOW_END = 2109

# We'll build modules manually from known content patterns using exec of sliced source
pass
