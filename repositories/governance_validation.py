"""Startup governance integrity queries (Phase E3)."""


def fetch_invalid_operator_roles(cursor) -> list[str]:
    cursor.execute(
        """
        SELECT DISTINCT role FROM operators
        WHERE role NOT IN ('administrator', 'review_officer', 'analyst', 'operations_manager')
        """
    )
    return [row[0] for row in cursor.fetchall()]


def count_orphaned_workflow_history(cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM workflow_history wh
        WHERE NOT EXISTS (SELECT 1 FROM applications a WHERE a.id = wh.application_id)
        """
    )
    return cursor.fetchone()[0] or 0


def count_orphaned_underwriting_decisions(cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM underwriting_decisions ud
        WHERE NOT EXISTS (SELECT 1 FROM applications a WHERE a.id = ud.application_id)
        """
    )
    return cursor.fetchone()[0] or 0


def fetch_operator_role_counts(cursor) -> dict:
    cursor.execute(
        """
        SELECT
            SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) AS active_count,
            SUM(CASE WHEN active = 0 THEN 1 ELSE 0 END) AS inactive_count
        FROM operators
        """
    )
    row = cursor.fetchone()
    return {
        "active_count": row["active_count"] or 0,
        "inactive_count": row["inactive_count"] or 0,
    }
