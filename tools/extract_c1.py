"""Extract Phase C1 modules from monolithic app.py."""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "app.py").read_text(encoding="utf-8")
LINES = SRC.splitlines()


def chunk(start: int, end: int) -> str:
    return "\n".join(LINES[start - 1 : end]) + "\n"


def save(path: str, header: str, start: int, end: int, transforms: list[tuple[str, str]] | None = None) -> None:
    text = chunk(start, end)
    if transforms:
        for old, new in transforms:
            text = text.replace(old, new)
    dest = ROOT / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(header.rstrip() + "\n\n" + text.lstrip(), encoding="utf-8")
    print(dest.relative_to(ROOT))


# Ensure package inits
for pkg in ("constants", "utils", "repositories", "services", "routes"):
    init = ROOT / pkg / "__init__.py"
    init.parent.mkdir(exist_ok=True)
    if not init.exists():
        init.write_text(f'"""MarginThrive {pkg} package."""\n', encoding="utf-8")

save("constants/app.py", "import os\nimport re", 22, 25)
save("constants/workflow.py", "", 27, 133)
save("constants/audit.py", "", 137, 169)
save("constants/reporting.py", "", 171, 215)
save("constants/schema.py", "", 217, 232)

save("utils/env.py", "", 235, 244)
save("utils/csrf.py", "import hmac\nimport secrets\n\nfrom flask import session", 247, 259)
save(
    "utils/auth.py",
    "import base64\nimport hmac\nimport os\nfrom functools import wraps\n\nfrom flask import Response, g, request",
    289,
    343,
)
save("utils/csv_export.py", "import csv\nimport io\n\nfrom flask import Response", 1600, 1639)

save(
    "repositories/database.py",
    """import sqlite3

from constants.app import DATABASE_PATH
from constants.schema import APPLICATIONS_SCHEMA_COLUMNS
from constants.workflow import DEFAULT_APPLICATION_STATUS, DEFAULT_RISK_LEVEL""",
    345,
    440,
    [
        ("def _get_db_connection():", "def get_db_connection():"),
        ("def init_db():", "def init_db():"),
        ("_get_db_connection()", "get_db_connection()"),
        ("_init_workflow_history_table", "init_workflow_history_table"),
        ("_init_officers_table", "init_officers_table"),
        ("_seed_officers_table", "seed_officers_table"),
    ],
)

save(
    "repositories/officers.py",
    """from repositories.database import get_db_connection""",
    478,
    537,
    [
        ("def _ensure_officer_registered", "def ensure_officer_registered"),
        ("def _fetch_registered_officers", "def fetch_registered_officers"),
        ("def _normalize_officer_name", "normalize_officer_name"),  # not in range - fix later
    ],
)

print("partial extract done - continue manually for remaining modules")
