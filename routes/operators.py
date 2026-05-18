from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from constants.operators import OPERATOR_ROLES, role_label
from repositories.database import get_db_connection
from repositories.operators import fetch_all_operators
from services.operators import change_operator_role, create_operator, set_operator_status
from utils.auth import require_administrator
from utils.csrf import ensure_session_csrf_token, validate_csrf
from utils.operational import current_operational_actor
from utils.ops_logging import log_governance_event

bp = Blueprint("operators", __name__)


@bp.route("/admin/operators", methods=["GET"])
@require_administrator
def admin_operators():
    conn = get_db_connection()
    cursor = conn.cursor()
    operators = fetch_all_operators(cursor)
    conn.close()

    return render_template(
        "operators.html",
        operators=operators,
        roles=OPERATOR_ROLES,
        role_labels={role: role_label(role) for role in OPERATOR_ROLES},
        csrf_token=ensure_session_csrf_token(),
        active_nav="operators",
        page_title="Operator accounts",
    )


@bp.route("/admin/operators", methods=["POST"])
@require_administrator
def admin_operators_create():
    if not validate_csrf(request.form.get("csrf_token", "")):
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("admin_operators"))

    operator_id, error = create_operator(request.form)
    if error:
        flash(error, "error")
        return redirect(url_for("admin_operators"))

    log_governance_event(
        "Operator account created",
        actor=current_operational_actor(),
        operator_id=operator_id,
        username=(request.form.get("username") or "").strip(),
        role=(request.form.get("role") or "").strip(),
    )
    flash(f"Operator account #{operator_id} created.", "success")
    return redirect(url_for("admin_operators"))


@bp.route("/admin/operators/<int:operator_id>/role", methods=["POST"])
@require_administrator
def admin_operators_update_role(operator_id: int):
    if not validate_csrf(request.form.get("csrf_token", "")):
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("admin_operators"))

    role = (request.form.get("role") or "").strip()
    error = change_operator_role(operator_id, role, g.operator["id"])
    if error:
        flash(error, "error")
    else:
        flash(f"Role updated for operator #{operator_id}.", "success")
    return redirect(url_for("admin_operators"))


@bp.route("/admin/operators/<int:operator_id>/status", methods=["POST"])
@require_administrator
def admin_operators_update_status(operator_id: int):
    if not validate_csrf(request.form.get("csrf_token", "")):
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("admin_operators"))

    action = (request.form.get("action") or "").strip()
    if action == "activate":
        active = True
    elif action == "deactivate":
        active = False
    else:
        flash("Unknown operator status action.", "error")
        return redirect(url_for("admin_operators"))

    error = set_operator_status(operator_id, active=active, acting_operator_id=g.operator["id"])
    if error:
        flash(error, "error")
    else:
        label = "activated" if active else "deactivated"
        log_governance_event(
            f"Operator account {label}",
            critical=not active,
            actor=current_operational_actor(),
            operator_id=operator_id,
            active=active,
        )
        flash(f"Operator #{operator_id} {label}.", "success")
    return redirect(url_for("admin_operators"))
