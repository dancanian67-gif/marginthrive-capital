"""Explicit SQLite write helpers with safe transactions (Phase E3)."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from typing import TypeVar

from repositories.database import get_db_connection
from utils.resilience import execute_with_sqlite_retry
from utils.ops_logging import log_db_commit, log_db_commit_failed

T = TypeVar("T")


def run_write_transaction(
    write_fn: Callable[[sqlite3.Cursor, sqlite3.Connection], T],
    *,
    operation_name: str = "database_write",
) -> T:
    """Open a connection, run write_fn, commit with retry, rollback on failure."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        result = write_fn(cursor, conn)
        t0 = time.perf_counter()
        try:
            execute_with_sqlite_retry(conn.commit, operation_name=operation_name)
        except Exception as exc:
            log_db_commit_failed(
                "Commit failed for write transaction",
                operation_name=operation_name,
                error=str(exc),
            )
            raise
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        log_db_commit(
            "Commit succeeded for write transaction",
            operation_name=operation_name,
            duration_ms=duration_ms,
        )
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def commit_connection(
    conn: sqlite3.Connection,
    *,
    operation_name: str = "database_commit",
) -> None:
    """Commit an open connection with SQLITE_BUSY retry."""
    t0 = time.perf_counter()
    try:
        execute_with_sqlite_retry(conn.commit, operation_name=operation_name)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        log_db_commit_failed(
            "Commit failed for open connection",
            operation_name=operation_name,
            error=str(exc),
            duration_ms=duration_ms,
        )
        raise
    duration_ms = round((time.perf_counter() - t0) * 1000, 2)
    log_db_commit(
        "Commit succeeded for open connection",
        operation_name=operation_name,
        duration_ms=duration_ms,
    )
