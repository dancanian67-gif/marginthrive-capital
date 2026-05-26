"""SQLite backup utilities (Phase D1, E2)."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone

from constants.app import DATABASE_PATH
from constants.ops import DEFAULT_BACKUP_DIR
from utils.ops_logging import log_startup
from utils.resilience import warn_backup_directory_unavailable


def backup_database(*, destination_dir: str | None = None) -> str:
    source = os.path.abspath(DATABASE_PATH)
    if not os.path.isfile(source):
        raise FileNotFoundError(f"Database file not found: {source}")

    backup_dir = destination_dir or os.getenv("BACKUP_DIR", DEFAULT_BACKUP_DIR)
    backup_dir = os.path.abspath(backup_dir)
    if not os.path.isdir(backup_dir):
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except OSError as exc:
            warn_backup_directory_unavailable(backup_dir, error=str(exc))
            raise

    if not os.access(backup_dir, os.W_OK):
        warn_backup_directory_unavailable(backup_dir, error="Directory is not writable")
        raise PermissionError(f"Backup directory is not writable: {backup_dir}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = os.path.splitext(os.path.basename(source))[0]
    destination = os.path.join(backup_dir, f"{base_name}_{timestamp}.db")
    shutil.copy2(source, destination)
    log_startup("Database backup created", source=source, destination=destination)
    return destination
