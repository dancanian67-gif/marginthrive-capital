#!/usr/bin/env python3
"""Print a lightweight deployment readiness checklist (Phase E4)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CHECKLIST = """
MarginThrive Capital — deployment checklist

Environment
  [ ] APP_ENV=production
  [ ] SECRET_KEY set (32+ random characters, not dev fallback)
  [ ] FLASK_DEBUG disabled
  [ ] SESSION_COOKIE_SECURE=true behind TLS
  [ ] TRUST_PROXY=true when using a reverse proxy
  [ ] FORCE_HTTPS=true when terminating TLS at proxy

Database
  [ ] DATABASE_PATH on persistent writable volume
  [ ] python tools/integrity_check.py passes (no FAIL)
  [ ] SQLite WAL mode active (warning-free diagnostics)
  [ ] Fresh backup taken: python tools/backup_database.py

Operators & governance
  [ ] At least one active administrator operator
  [ ] Operator roles reviewed (administrator / operations_manager / review_officer / analyst)
  [ ] RBAC expectations communicated to the team

Runtime verification
  [ ] python tools/operational_diagnostics.py — overall OK or WARN only
  [ ] python tools/smoke_test.py — all tests pass (staging with isolated DB)
  [ ] GET /health — 200
  [ ] GET /health/ready — 200
  [ ] Sign-in and sign-out verified

Process
  [ ] Gunicorn: gunicorn --bind 0.0.0.0:8000 wsgi:application
  [ ] LOG_FILE or centralized log collection configured
  [ ] BACKUP_DIR exists and is writable
  [ ] Incident runbook: docs/OPERATIONS.md
"""


def main() -> int:
    print(CHECKLIST.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
