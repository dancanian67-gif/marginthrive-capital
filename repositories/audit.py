from constants.audit import WORKFLOW_HISTORY_LIMIT
from constants.reporting import REPORT_EXPORT_MAX_ROWS
from services.analytics_query import analytics_datetime_clause
from utils.db_compat import datetime_order_expression, non_empty_timestamp_predicate


def init_workflow_history_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            batch_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            field_name TEXT,
            old_value TEXT,
            new_value TEXT,
            previous_state TEXT NOT NULL,
            new_state TEXT NOT NULL,
            actor TEXT NOT NULL,
            context_notes TEXT NOT NULL DEFAULT '',
            is_critical INTEGER NOT NULL DEFAULT 0,
            transition_warning TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workflow_history_application
        ON workflow_history (application_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workflow_history_batch
        ON workflow_history (batch_id)
        """
    )


def fetch_workflow_history_rows(cursor, application_id: int, limit: int = WORKFLOW_HISTORY_LIMIT) -> list:
    cursor.execute(
        """
        SELECT
            id,
            application_id,
            batch_id,
            action_type,
            field_name,
            old_value,
            new_value,
            previous_state,
            new_state,
            actor,
            context_notes,
            is_critical,
            transition_warning,
            created_at
        FROM workflow_history
        WHERE application_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (application_id, limit),
    )
    return cursor.fetchall()


_AUDIT_EXPORT_COLUMNS = (
    "id",
    "application_id",
    "business_name",
    "batch_id",
    "action_type",
    "field_name",
    "old_value",
    "new_value",
    "actor",
    "context_notes",
    "is_critical",
    "transition_warning",
    "created_at",
)


def _audit_export_where(range_key: str, application_id: int | None) -> tuple[str, list]:
    created_clause, created_params = analytics_datetime_clause(range_key, "wh.created_at")
    application_clause = ""
    application_params: list = []
    if application_id is not None:
        application_clause = " AND wh.application_id = ?"
        application_params.append(application_id)
    where_sql = (
        f"WHERE {non_empty_timestamp_predicate('wh.created_at')}"
        f"{created_clause}{application_clause}"
    )
    return where_sql, [*created_params, *application_params]


def count_audit_history_for_export(
    cursor,
    range_key: str,
    application_id: int | None = None,
) -> int:
    where_sql, params = _audit_export_where(range_key, application_id)
    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM workflow_history wh
        {where_sql}
        """,
        params,
    )
    return cursor.fetchone()[0] or 0


def iter_audit_history_for_export(
    cursor,
    range_key: str,
    application_id: int | None = None,
    limit: int = REPORT_EXPORT_MAX_ROWS,
):
    where_sql, params = _audit_export_where(range_key, application_id)
    cursor.execute(
        f"""
        SELECT
            wh.id,
            wh.application_id,
            COALESCE(a.business_name, '') AS business_name,
            wh.batch_id,
            wh.action_type,
            wh.field_name,
            wh.old_value,
            wh.new_value,
            wh.actor,
            wh.context_notes,
            wh.is_critical,
            wh.transition_warning,
            wh.created_at
        FROM workflow_history wh
        LEFT JOIN applications a ON a.id = wh.application_id
        {where_sql}
        ORDER BY {datetime_order_expression('wh.created_at')} DESC, wh.id DESC
        LIMIT ?
        """,
        (*params, limit),
    )
    for row in cursor:
        yield {column: row[column] for column in _AUDIT_EXPORT_COLUMNS}


def fetch_audit_history_for_export(
    cursor,
    range_key: str,
    application_id: int | None = None,
    limit: int = REPORT_EXPORT_MAX_ROWS,
) -> list[dict]:
    return list(iter_audit_history_for_export(cursor, range_key, application_id, limit))


def fetch_governance_audit_summary(cursor, range_key: str) -> dict:
    created_clause, created_params = analytics_datetime_clause(range_key, "created_at")
    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total_events,
            SUM(CASE WHEN is_critical = 1 THEN 1 ELSE 0 END) AS critical_events,
            COUNT(DISTINCT batch_id) AS workflow_batches,
            COUNT(DISTINCT actor) AS unique_operators,
            COUNT(DISTINCT application_id) AS applications_touched
        FROM workflow_history
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        """,
        created_params,
    )
    row = cursor.fetchone()
    return {
        "total_events": row["total_events"] or 0,
        "critical_events": row["critical_events"] or 0,
        "workflow_batches": row["workflow_batches"] or 0,
        "unique_operators": row["unique_operators"] or 0,
        "applications_touched": row["applications_touched"] or 0,
    }
