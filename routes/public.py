from flask import Blueprint, redirect, render_template, request, session

from constants.app import DATABASE_PATH
from constants.workflow import DEFAULT_APPLICATION_STATUS
from services.audit import log_application_created
from services.intake import is_valid_application_form
from utils.db_write import run_write_transaction
from utils.csrf import ensure_session_csrf_token, validate_csrf
from utils.ops_logging import (
    log_application_persistence_failed,
    log_application_submission,
    log_application_submission_rejected,
)

bp = Blueprint("public", __name__)


@bp.route("/")
def home():
    csrf_token = ensure_session_csrf_token()
    return render_template("index.html", csrf_token=csrf_token)


@bp.route("/apply", methods=["POST"])
def apply():
    data = request.form
    form_product = (data.get("product") or "").strip()
    form_email = (data.get("email") or "").strip()
    form_phone_number = (data.get("phone_number") or "").strip()
    email_domain = (form_email.split("@", 1)[1] if "@" in form_email else "")
    revenue_raw = (data.get("revenue") or "").strip()
    business_name = (data.get("business_name") or "").strip()

    if not validate_csrf(data.get("csrf_token", "")):
        log_application_submission_rejected(
            "Public intake rejected: CSRF validation failed",
            product=form_product,
            email_domain=email_domain,
            phone_number=form_phone_number[:20],
            revenue_raw=revenue_raw,
        )
        return redirect("/")

    if not is_valid_application_form(data):
        log_application_submission_rejected(
            "Public intake rejected: form validation failed",
            business_name=business_name[:80],
            product=form_product,
            email_domain=email_domain,
            phone_number=form_phone_number[:20],
            revenue_raw=revenue_raw,
        )
        return redirect("/")

    log_application_submission(
        "Public intake accepted; persisting application",
        business_name=business_name[:80],
        product=form_product,
        email_domain=email_domain,
        phone_number=form_phone_number[:20],
        revenue_raw=revenue_raw,
        database_path=DATABASE_PATH,
    )

    try:
        def write_fn(cursor, conn):
            cursor.execute(
                """
                INSERT INTO applications (
                    business_name,
                    owner_name,
                    email,
                    phone_number,
                    revenue,
                    product,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    data["business_name"].strip(),
                    data["owner_name"].strip(),
                    data["email"].strip(),
                    data["phone_number"].strip().replace(" ", ""),
                    data["revenue"],
                    data["product"].strip(),
                    DEFAULT_APPLICATION_STATUS,
                ),
            )
            application_id = cursor.lastrowid
            log_application_created(cursor, application_id)
            return application_id

        application_id = run_write_transaction(
            write_fn,
            operation_name="public_intake_application_commit",
        )
        log_application_submission(
            "Public intake persisted application",
            application_id=application_id,
            database_path=DATABASE_PATH,
        )
    except Exception as exc:
        log_application_persistence_failed(
            "Public intake persistence failed",
            error=str(exc),
            business_name=business_name[:80],
            product=form_product,
            email_domain=email_domain,
            phone_number=form_phone_number[:20],
            revenue_raw=revenue_raw,
            database_path=DATABASE_PATH,
        )
        # Avoid exposing details to end users; operator logs contain full context.
        return redirect("/")

    return redirect("/")
