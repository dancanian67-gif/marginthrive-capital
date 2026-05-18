"""SQLite backup utilities (Phase D1)."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone

from constants.app import DATABASE_PATH
from utils.ops_logging import log_startup


def backup_database(*, destination_dir: str | None = None) -> str:
    source = os.path.abspath(DATABASE_PATH)
    if not os.path.isfile(source):
        raise FileNotFoundError(f"Database file not found: {source}")

    backup_dir = destination_dir or os.getenv("BACKUP_DIR", "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = os.path.splitext(os.path.basename(source))[0]
    destination = os.path.join(backup_dir, f"{base_name}_{timestamp}.db")
    shutil.copy2(source, destination)
    log_startup("Database backup created", source=source, destination=destination)
    return destination
