import os
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

def init_operators_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS operators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'review_officer',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_login_at TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operators_active
        ON operators (active, username COLLATE NOCASE)
        """
    )


def count_operators(cursor) -> int:
    cursor.execute("SELECT COUNT(*) AS total FROM operators")
    return cursor.fetchone()["total"] or 0


def seed_bootstrap_operator(cursor) -> None:
    """Create the first administrator from env when no operators exist."""
    if count_operators(cursor) > 0:
        return

    username = (os.getenv("ADMIN_USERNAME") or "").strip()
    password = os.getenv("ADMIN_PASSWORD") or ""
    if not username or not password:
        return

    email = (os.getenv("ADMIN_EMAIL") or f"{username}@marginthrive.local").strip().lower()
    display_name = (os.getenv("ADMIN_DISPLAY_NAME") or username).strip()
    password_hash = generate_password_hash(password)

    cursor.execute(
        """
        INSERT INTO operators (
            username,
            email,
            password_hash,
            display_name,
            role,
            active
        )
        VALUES (?, ?, ?, ?, 'administrator', 1)
        """,
        (username, email, password_hash, display_name),
    )


def fetch_operator_by_id(cursor, operator_id: int) -> sqlite3.Row | None:
    cursor.execute(
        """
        SELECT id, username, email, display_name, role, active, created_at, updated_at, last_login_at
        FROM operators
        WHERE id = ?
        """,
        (operator_id,),
    )
    return cursor.fetchone()


def fetch_operator_by_username(cursor, identity: str) -> sqlite3.Row | None:
    normalized = (identity or "").strip()
    if not normalized:
        return None
    cursor.execute(
        """
        SELECT
            id,
            username,
            email,
            password_hash,
            display_name,
            role,
            active,
            created_at,
            updated_at,
            last_login_at
        FROM operators
        WHERE active = 1
          AND (username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE)
        """,
        (normalized, normalized.lower()),
    )
    return cursor.fetchone()


def fetch_all_operators(cursor) -> list[sqlite3.Row]:
    cursor.execute(
        """
        SELECT id, username, email, display_name, role, active, created_at, updated_at, last_login_at
        FROM operators
        ORDER BY active DESC, username COLLATE NOCASE ASC
        """
    )
    return cursor.fetchall()


def authenticate_operator(cursor, identity: str, password: str) -> sqlite3.Row | None:
    row = fetch_operator_by_username(cursor, identity)
    if row is None:
        return None
    if not check_password_hash(row["password_hash"], password):
        return None
    return row


def record_operator_login(cursor, operator_id: int) -> None:
    cursor.execute(
        """
        UPDATE operators
        SET last_login_at = datetime('now'), updated_at = datetime('now')
        WHERE id = ?
        """,
        (operator_id,),
    )


def create_operator_record(
    cursor,
    *,
    username: str,
    email: str,
    password_hash: str,
    display_name: str,
    role: str,
) -> int:
    cursor.execute(
        """
        INSERT INTO operators (username, email, password_hash, display_name, role, active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (username, email, password_hash, display_name, role),
    )
    return cursor.lastrowid


def update_operator_role(cursor, operator_id: int, role: str) -> bool:
    cursor.execute(
        """
        UPDATE operators
        SET role = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (role, operator_id),
    )
    return cursor.rowcount > 0


def set_operator_active(cursor, operator_id: int, active: bool) -> bool:
    cursor.execute(
        """
        UPDATE operators
        SET active = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (1 if active else 0, operator_id),
    )
    return cursor.rowcount > 0


def username_exists(cursor, username: str, exclude_id: int | None = None) -> bool:
    if exclude_id is not None:
        cursor.execute(
            """
            SELECT 1 FROM operators
            WHERE username = ? COLLATE NOCASE AND id != ?
            LIMIT 1
            """,
            (username, exclude_id),
        )
    else:
        cursor.execute(
            "SELECT 1 FROM operators WHERE username = ? COLLATE NOCASE LIMIT 1",
            (username,),
        )
    return cursor.fetchone() is not None


def email_exists(cursor, email: str, exclude_id: int | None = None) -> bool:
    normalized = email.strip().lower()
    if exclude_id is not None:
        cursor.execute(
            """
            SELECT 1 FROM operators
            WHERE email = ? COLLATE NOCASE AND id != ?
            LIMIT 1
            """,
            (normalized, exclude_id),
        )
    else:
        cursor.execute(
            "SELECT 1 FROM operators WHERE email = ? COLLATE NOCASE LIMIT 1",
            (normalized,),
        )
    return cursor.fetchone() is not None


def count_active_administrators(cursor, exclude_id: int | None = None) -> int:
    if exclude_id is not None:
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM operators
            WHERE role = 'administrator' AND active = 1 AND id != ?
            """,
            (exclude_id,),
        )
    else:
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM operators
            WHERE role = 'administrator' AND active = 1
            """
        )
    return cursor.fetchone()["total"] or 0
