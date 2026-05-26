"""Export timing, row-count warnings, and streaming helpers (Phase E2)."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

from repositories.database import get_db_connection
from utils.resilience import warn_large_export, warn_slow_export


def stream_rows_from_db(
    setup: Callable,
    *,
    export_type: str | None = None,
    filename: str | None = None,
    row_count: int | None = None,
    start_time: float | None = None,
) -> Iterator[dict]:
    """Keep the SQLite connection open until the export iterator is exhausted."""

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for row in setup(cursor):
            yield row
    finally:
        conn.close()
        if export_type and start_time is not None:
            warn_slow_export(
                time.perf_counter() - start_time,
                export_type=export_type,
                row_count=row_count,
                filename=filename,
            )


def monitored_export(
    export_type: str,
    filename: str,
    row_count: int,
    *,
    start_time: float | None = None,
) -> None:
    warn_large_export(row_count, export_type=export_type, filename=filename)
    if start_time is not None:
        elapsed = time.perf_counter() - start_time
        warn_slow_export(elapsed, export_type=export_type, row_count=row_count, filename=filename)


def count_export_rows(cursor, count_sql: str, params: list) -> int:
    cursor.execute(count_sql, params)
    row = cursor.fetchone()
    return int(row[0] if row else 0)
