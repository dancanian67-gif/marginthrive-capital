from functools import wraps

from flask import Response, g, redirect, request, session, url_for

from constants.operators import (
    SESSION_OPERATOR_DISPLAY_NAME,
    SESSION_OPERATOR_ID,
    SESSION_OPERATOR_ROLE,
    SESSION_OPERATOR_USERNAME,
    can_manage_operators,
    role_label,
)
from repositories.database import get_db_connection
from repositories.operators import fetch_operator_by_id


def operator_audit_label(operator: dict) -> str:
    username = operator["username"]
    display_name = (operator.get("display_name") or "").strip()
    if display_name and display_name.casefold() != username.casefold():
        return f"{display_name} ({username})"
    return username


def operator_from_session() -> dict | None:
    operator_id = session.get(SESSION_OPERATOR_ID)
    if not operator_id:
        return None

    return {
        "id": operator_id,
        "username": session.get(SESSION_OPERATOR_USERNAME, ""),
        "role": session.get(SESSION_OPERATOR_ROLE, ""),
        "display_name": session.get(SESSION_OPERATOR_DISPLAY_NAME, ""),
    }


def establish_operator_session(operator_row) -> None:
    session.clear()
    session.permanent = True
    session[SESSION_OPERATOR_ID] = operator_row["id"]
    session[SESSION_OPERATOR_USERNAME] = operator_row["username"]
    session[SESSION_OPERATOR_ROLE] = operator_row["role"]
    session[SESSION_OPERATOR_DISPLAY_NAME] = operator_row["display_name"] or operator_row["username"]


def clear_operator_session() -> None:
    session.clear()


def load_active_operator(operator_id: int) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    row = fetch_operator_by_id(cursor, operator_id)
    conn.close()
    if row is None or not row["active"]:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "display_name": row["display_name"] or row["username"],
        "role": row["role"],
        "active": bool(row["active"]),
        "role_label": role_label(row["role"]),
    }


def get_request_actor() -> str:
    operator = getattr(g, "operator", None) or operator_from_session()
    if operator:
        return operator_audit_label(operator)
    return "unknown-operator"


def safe_login_redirect(candidate: str | None) -> str:
    target = (candidate or "").strip()
    if target.startswith("/admin") and "://" not in target and not target.startswith("//"):
        return target
    return url_for("admin_overview")


def require_admin_auth(route_fn):
    """Require an authenticated, active operator session (replaces HTTP Basic Auth)."""

    @wraps(route_fn)
    def wrapper(*args, **kwargs):
        session_operator = operator_from_session()
        if not session_operator:
            return redirect(url_for("admin_login", next=request.full_path))

        operator = load_active_operator(session_operator["id"])
        if operator is None:
            clear_operator_session()
            return redirect(url_for("admin_login", next=request.full_path))

        g.operator = operator
        g.admin_actor = operator_audit_label(operator)
        return route_fn(*args, **kwargs)

    return wrapper


def require_administrator(route_fn):
    """Require administrator role for operator management actions."""

    @wraps(route_fn)
    @require_admin_auth
    def wrapper(*args, **kwargs):
        operator = getattr(g, "operator", None)
        if not operator or not can_manage_operators(operator["role"]):
            return Response("Administrator access required.", status=403)
        return route_fn(*args, **kwargs)

    return wrapper
