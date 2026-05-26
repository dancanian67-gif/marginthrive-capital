"""Operational resilience warnings and safe SQLite retries (Phase E2)."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from typing import Any, TypeVar

from constants.ops import (
    ANALYTICS_OVERSIZED_RANGE_KEYS,
    EXPORT_SLOW_SECONDS,
    EXPORT_WARN_ROW_THRESHOLD,
)
from utils.ops_logging import log_operational_warning

T = TypeVar("T")

SQLITE_LOCKED_CODES = frozenset({5})  # SQLITE_BUSY


def warn_oversized_analytics_range(range_key: str) -> None:
    if range_key in ANALYTICS_OVERSIZED_RANGE_KEYS:
        log_operational_warning(
            "Large analytics range may increase query time",
            range_key=range_key,
            hint="Prefer 7d/30d for routine dashboards unless full history is required.",
        )


def warn_large_export(row_count: int, *, export_type: str, filename: str | None = None) -> None:
    if row_count >= EXPORT_WARN_ROW_THRESHOLD:
        log_operational_warning(
            "Export row count exceeds recommended threshold",
            export_type=export_type,
            row_count=row_count,
            threshold=EXPORT_WARN_ROW_THRESHOLD,
            filename=filename or "",
        )


def warn_slow_export(
    elapsed_seconds: float,
    *,
    export_type: str,
    row_count: int | None = None,
    filename: str | None = None,
) -> None:
    if elapsed_seconds >= EXPORT_SLOW_SECONDS:
        log_operational_warning(
            "Export generation exceeded expected duration",
            export_type=export_type,
            elapsed_seconds=round(elapsed_seconds, 2),
            row_count=row_count,
            filename=filename or "",
        )


def warn_missing_directory(path: str, *, purpose: str) -> None:
    log_operational_warning(
        "Expected directory is missing",
        path=path,
        purpose=purpose,
    )


def warn_backup_directory_unavailable(path: str, *, error: str | None = None) -> None:
    log_operational_warning(
        "Backup directory is not available",
        path=path,
        error=error or "",
    )


def warn_sqlite_lock_retry(attempt: int, *, operation: str) -> None:
    log_operational_warning(
        "SQLite database locked; retrying",
        operation=operation,
        attempt=attempt,
    )


def execute_with_sqlite_retry(
    operation: Callable[[], T],
    *,
    operation_name: str = "database_write",
    max_attempts: int = 3,
    delay_seconds: float = 0.05,
) -> T:
    """Retry on SQLITE_BUSY without crashing the request path."""
    last_error: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if getattr(exc, "sqlite_errorcode", None) not in SQLITE_LOCKED_CODES:
                raise
            last_error = exc
            if attempt < max_attempts:
                warn_sqlite_lock_retry(attempt, operation=operation_name)
                time.sleep(delay_seconds * attempt)
    assert last_error is not None
    raise last_error
