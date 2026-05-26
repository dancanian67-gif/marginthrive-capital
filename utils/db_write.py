"""Explicit SQLite write helpers with safe transactions (Phase E3)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import TypeVar

from repositories.database import get_db_connection
from utils.resilience import execute_with_sqlite_retry

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
        execute_with_sqlite_retry(conn.commit, operation_name=operation_name)
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
    execute_with_sqlite_retry(conn.commit, operation_name=operation_name)
