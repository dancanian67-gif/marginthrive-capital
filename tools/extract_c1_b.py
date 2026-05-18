"""Extract remaining Phase C1 modules."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
LINES = (ROOT / "app.py").read_text(encoding="utf-8").splitlines()


def chunk(start: int, end: int) -> str:
    return "\n".join(LINES[start - 1 : end]) + "\n"


def save(path: str, header: str, start: int, end: int) -> None:
    dest = ROOT / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(header.rstrip() + "\n\n" + chunk(start, end).lstrip(), encoding="utf-8")
    print(dest.relative_to(ROOT))


save(
    "repositories/audit.py",
    "",
    443,
    505,
)
save(
    "repositories/audit.py",
    (ROOT / "repositories/audit.py").read_text(encoding="utf-8")
    + "\n"
    + chunk(867, 927),
    1,
    1,
)
