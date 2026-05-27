"""Isolated smoke-test harness with temporary SQLite database (Phase E4)."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SMOKE_ADMIN_USERNAME = "smoke_admin"
SMOKE_ADMIN_PASSWORD = "SmokeTestAdmin99!"
SMOKE_ANALYST_USERNAME = "smoke_analyst"
SMOKE_ANALYST_PASSWORD = "SmokeTestAnalyst99!"
SMOKE_REVIEW_OFFICER_USERNAME = "smoke_review"
SMOKE_REVIEW_OFFICER_PASSWORD = "SmokeTestReview99!"


def configure_isolated_environment() -> str:
    """Point the app at a fresh database and bootstrap credentials."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault("FLASK_ENV", "development")
    os.environ.setdefault("FLASK_DEBUG", "false")
    os.environ["DATABASE_PATH"] = db_path
    os.environ["SECRET_KEY"] = "smoke-test-secret-key-32-characters-min"
    os.environ["ADMIN_USERNAME"] = SMOKE_ADMIN_USERNAME
    os.environ["ADMIN_PASSWORD"] = SMOKE_ADMIN_PASSWORD
    os.environ["ADMIN_EMAIL"] = "smoke_admin@marginthrive.test"
    os.environ["ADMIN_DISPLAY_NAME"] = "Smoke Test Admin"

    import constants.app as app_constants

    app_constants.DATABASE_PATH = db_path
    return db_path


def create_test_application(cursor) -> int:
    cursor.execute(
        """
        INSERT INTO applications (
            business_name, owner_name, email, revenue, product, status,
            created_at, updated_at
        )
        VALUES ('Smoke Corp', 'Smoke Owner', 'smoke@test.local', 50000, 'MarginPro',
                'New applicant', datetime('now'), datetime('now'))
        """
    )
    return cursor.lastrowid


def seed_analyst_operator(cursor) -> None:
    cursor.execute(
        "SELECT id FROM operators WHERE username = ? COLLATE NOCASE",
        (SMOKE_ANALYST_USERNAME,),
    )
    if cursor.fetchone():
        return
    cursor.execute(
        """
        INSERT INTO operators (username, email, password_hash, display_name, role, active)
        VALUES (?, ?, ?, ?, 'analyst', 1)
        """,
        (
            SMOKE_ANALYST_USERNAME,
            "smoke_analyst@marginthrive.test",
            generate_password_hash(SMOKE_ANALYST_PASSWORD),
            "Smoke Analyst",
        ),
    )


def seed_review_officer_operator(cursor) -> None:
    cursor.execute(
        "SELECT id FROM operators WHERE username = ? COLLATE NOCASE",
        (SMOKE_REVIEW_OFFICER_USERNAME,),
    )
    if cursor.fetchone():
        return
    cursor.execute(
        """
        INSERT INTO operators (username, email, password_hash, display_name, role, active)
        VALUES (?, ?, ?, ?, 'review_officer', 1)
        """,
        (
            SMOKE_REVIEW_OFFICER_USERNAME,
            "smoke_review@marginthrive.test",
            generate_password_hash(SMOKE_REVIEW_OFFICER_PASSWORD),
            "Smoke Review Officer",
        ),
    )


def extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if not match:
        raise AssertionError("CSRF token not found in response")
    return match.group(1)


def login_client(client, *, username: str, password: str) -> None:
    response = client.get("/admin/login")
    csrf = extract_csrf(response.get_data(as_text=True))
    client.post(
        "/admin/login",
        data={"identity": username, "password": password, "csrf_token": csrf},
        follow_redirects=True,
    )
