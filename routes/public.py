from flask import Blueprint, redirect, render_template, request, session

from constants.workflow import DEFAULT_APPLICATION_STATUS
from repositories.database import get_db_connection
from services.audit import log_application_created
from services.intake import is_valid_application_form
from utils.csrf import ensure_session_csrf_token, validate_csrf

bp = Blueprint("public", __name__)


@bp.route("/")
def home():
    csrf_token = ensure_session_csrf_token()
    return render_template("index.html", csrf_token=csrf_token)


@bp.route("/apply", methods=["POST"])
def apply():
    data = request.form
    if not validate_csrf(data.get("csrf_token", "")):
        return redirect("/")

    if not is_valid_application_form(data):
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO applications (
            business_name,
            owner_name,
            email,
            revenue,
            product,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        (
            data["business_name"].strip(),
            data["owner_name"].strip(),
            data["email"].strip(),
            data["revenue"],
            data["product"].strip(),
            DEFAULT_APPLICATION_STATUS,
        ),
    )
    application_id = cursor.lastrowid
    log_application_created(cursor, application_id)

    conn.commit()
    conn.close()

    return redirect("/")
