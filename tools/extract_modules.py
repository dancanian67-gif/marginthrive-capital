"""Extract app.py sections into Phase C1 module files."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
LINES = (ROOT / "app.py").read_text(encoding="utf-8").splitlines(keepends=True)


def extract(start: int, end: int) -> str:
    return "".join(LINES[start - 1 : end])


MODULES: list[tuple[str, str, int, int]] = [
    # path, header, start, end (inclusive line numbers from app.py)
]

if __name__ == "__main__":
    print("Use manual module creation")
