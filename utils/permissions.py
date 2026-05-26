"""Reusable operational RBAC enforcement (Phase E3)."""

from __future__ import annotations

from functools import wraps

from flask import flash, g, redirect, request, url_for

from constants.permissions import (
    PERMISSION_DENIED_MESSAGES,
    permissions_for_role,
)
from utils.auth import require_admin_auth
from utils.governance import log_permission_denied


def role_has_permission(role: str, permission: str) -> bool:
    return permission in permissions_for_role(role)


def operator_has_permission(operator: dict | None, permission: str) -> bool:
    if not operator:
        return False
    return role_has_permission(operator.get("role", ""), permission)


def permission_denied_message(permission: str) -> str:
    return PERMISSION_DENIED_MESSAGES.get(
        permission,
        "You do not have permission to perform that action.",
    )


def _safe_redirect_target(*, application_id: int | None = None) -> str:
    if application_id is not None:
        return url_for("admin_application_detail", application_id=application_id)
    next_url = (request.args.get("next") or request.form.get("return_url") or "").strip()
    if next_url.startswith("/admin") and "://" not in next_url and not next_url.startswith("//"):
        return next_url
    referrer = (request.referrer or "").strip()
    if referrer.startswith("/admin") and "://" not in referrer:
        return referrer
    if request.path.startswith("/admin/analytics") or request.path.startswith("/admin/reports"):
        return url_for("admin_analytics")
    if request.path.startswith("/admin/export"):
        return url_for("admin_reports")
    return url_for("admin_overview")


def deny_operator_access(
    permission: str,
    *,
    application_id: int | None = None,
    action: str | None = None,
):
    operator = getattr(g, "operator", None)
    log_permission_denied(
        permission,
        operator=operator,
        path=request.path,
        method=request.method,
        action=action or permission,
    )
    flash(permission_denied_message(permission), "error")
    return redirect(_safe_redirect_target(application_id=application_id))


def require_permission(permission: str, *, action: str | None = None):
    """Stack on authenticated session; flash and redirect when permission is missing."""

    def decorator(route_fn):
        @wraps(route_fn)
        @require_admin_auth
        def wrapper(*args, **kwargs):
            operator = getattr(g, "operator", None)
            if not operator_has_permission(operator, permission):
                app_id = kwargs.get("application_id")
                if app_id is None and kwargs.get("operator_id"):
                    return deny_operator_access(
                        permission,
                        action=action,
                    )
                return deny_operator_access(
                    permission,
                    application_id=app_id,
                    action=action or permission,
                )
            return route_fn(*args, **kwargs)

        return wrapper

    return decorator


def require_administrator(route_fn):
    """Administrator-only operator management (replaces raw 403 responses)."""

    from constants.permissions import PERM_MANAGE_OPERATORS

    return require_permission(PERM_MANAGE_OPERATORS, action="manage_operators")(route_fn)
