#!/usr/bin/env python3
"""Database and governance integrity check (Phase E4).

Usage:
    python tools/integrity_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv()

from factory import initialize_application
from repositories.database import get_db_connection
from utils.integrity_checks import run_operational_integrity_checks


def main() -> int:
    initialize_application()
    conn = get_db_connection()
    cursor = conn.cursor()
    report = run_operational_integrity_checks(cursor)
    conn.close()

    counts = report["counts"]
    print("MarginThrive integrity check")
    print(f"Overall: {report['overall'].upper()}")
    print(f"OK: {counts.get('ok', 0)}  WARN: {counts.get('warn', 0)}  FAIL: {counts.get('fail', 0)}")
    print()
    for check in report["checks"]:
        if check["status"] != "ok":
            print(f"[{check['status'].upper()}] {check['name']}: {check['message']}")

    return 0 if report["overall"] != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())
