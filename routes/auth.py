from flask import Blueprint, flash, redirect, render_template, request, url_for

from repositories.database import get_db_connection
from repositories.operators import authenticate_operator, count_operators, record_operator_login
from utils.auth import clear_operator_session, establish_operator_session, safe_login_redirect
from utils.csrf import ensure_session_csrf_token, validate_csrf
from utils.login_protection import (
    is_login_locked,
    login_attempt_key,
    register_failed_login,
    register_successful_login,
)
from utils.ops_logging import log_auth_event, log_auth_warning

bp = Blueprint("auth", __name__)


@bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        csrf_token = ensure_session_csrf_token()
        return render_template(
            "login.html",
            csrf_token=csrf_token,
            page_title="Operator sign in",
            next_url=safe_login_redirect(request.args.get("next")),
        )

    if not validate_csrf(request.form.get("csrf_token", "")):
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("admin_login"))

    identity = (request.form.get("identity") or "").strip()
    password = request.form.get("password") or ""
    if not identity or not password:
        flash("Enter your username or email and password.", "error")
        return redirect(url_for("admin_login", next=request.form.get("next")))

    attempt_key = login_attempt_key(identity)
    if is_login_locked(attempt_key):
        flash("Too many failed sign-in attempts. Please wait and try again.", "error")
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    if count_operators(cursor) == 0:
        conn.close()
        log_auth_warning(
            "auth.login.unavailable",
            "Login attempted before any operator accounts exist",
            identity=identity,
        )
        flash(
            "No operator accounts exist yet. Set ADMIN_USERNAME and ADMIN_PASSWORD, then restart the app.",
            "error",
        )
        return redirect(url_for("admin_login"))

    operator = authenticate_operator(cursor, identity, password)
    if operator is None:
        conn.close()
        register_failed_login(attempt_key, identity=identity)
        flash("Invalid credentials or inactive operator account.", "error")
        return redirect(url_for("admin_login", next=request.form.get("next")))

    record_operator_login(cursor, operator["id"])
    conn.commit()
    conn.close()

    register_successful_login(attempt_key)
    establish_operator_session(operator)
    log_auth_event(
        "auth.login.success",
        "Operator signed in",
        operator_id=operator["id"],
        username=operator["username"],
        role=operator["role"],
    )
    flash(f"Signed in as {operator['username']}.", "success")
    return redirect(safe_login_redirect(request.form.get("next")))


@bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    if not validate_csrf(request.form.get("csrf_token", "")):
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("admin_login"))

    from utils.auth import operator_audit_label, operator_from_session

    session_operator = operator_from_session()
    actor = operator_audit_label(session_operator) if session_operator else "unknown-operator"
    clear_operator_session()
    log_auth_event("auth.logout", "Operator signed out", actor=actor)
    flash("You have been signed out.", "info")
    return redirect(url_for("admin_login"))
