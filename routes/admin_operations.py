"""Recovered Phase F/G admin routes (collections, promises, notifications, exports)."""

from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from constants.collections import (
    COLLECTIONS_PRIORITIES,
    COLLECTIONS_RISK_LEVELS,
    COLLECTIONS_STATUSES,
    DELINQUENCY_BUCKETS,
)
from constants.permissions import (
    PERM_EXPORT,
    PERM_MUTATE_COLLECTIONS,
    PERM_VIEW_COLLECTIONS,
    PERM_VIEW_OPERATIONS,
)
from constants.promises import PROMISE_QUEUE_FILTER_LABELS, PROMISE_QUEUE_FILTERS
from constants.reporting import (
    COLLECTIONS_ACTIVITY_EXPORT_COLUMNS,
    COLLECTIONS_DELINQUENT_EXPORT_COLUMNS,
    COLLECTIONS_ESCALATION_REPORT_COLUMNS,
    COLLECTIONS_EXPOSURE_EXPORT_COLUMNS,
    COLLECTIONS_OFFICER_RECOVERY_EXPORT_COLUMNS,
    COLLECTIONS_OUTCOME_DISTRIBUTION_EXPORT_COLUMNS,
    COLLECTIONS_RECOVERY_SUMMARY_EXPORT_COLUMNS,
    COLLECTIONS_WORKLOAD_EXPORT_COLUMNS,
    NOTIFICATIONS_ACK_METRICS_EXPORT_COLUMNS,
    NOTIFICATIONS_ALERTS_EXPORT_COLUMNS,
    NOTIFICATIONS_CRITICAL_EVENTS_EXPORT_COLUMNS,
    NOTIFICATIONS_GOVERNANCE_EXPORT_COLUMNS,
    NOTIFICATIONS_UNRESOLVED_EXPORT_COLUMNS,
    PROMISES_ACTIVE_EXPORT_COLUMNS,
    PROMISES_BROKEN_EXPORT_COLUMNS,
    PROMISES_OFFICER_PERFORMANCE_EXPORT_COLUMNS,
    PROMISES_OVERDUE_EXPORT_COLUMNS,
    PROMISES_REPAYMENT_CONVERSION_EXPORT_COLUMNS,
    REPORT_EXPORT_MAX_ROWS,
)
from repositories.applications import fetch_application
from repositories.collections import (
    fetch_collections_activity_for_export,
    fetch_collections_delinquency_distribution,
    fetch_collections_history_rows,
    fetch_collections_officer_workload,
    fetch_collections_queue_kpis,
    iter_collections_queue_for_export,
)
from repositories.collections_intelligence import (
    fetch_application_intelligence_context,
    fetch_escalation_report_rows,
    fetch_officer_recovery_performance,
    fetch_recovery_outcome_distribution,
    iter_collections_recovery_summary_export,
)
from repositories.database import get_db_connection
from repositories.loans import fetch_repayment_rows
from repositories.notifications import iter_operational_alerts_export
from repositories.notifications import (
    fetch_critical_event_summary_export,
    fetch_governance_alerts_export,
    fetch_operator_acknowledgement_metrics_export,
    fetch_unresolved_notifications_export,
)
from repositories.officers import fetch_distinct_officers
from repositories.promises import (
    fetch_promise_by_id,
    fetch_promise_history_rows,
    fetch_promise_summary_for_application,
    fetch_repayment_conversion_rows,
    iter_active_promises_export,
    fetch_broken_commitments_export,
    fetch_overdue_commitments_export,
    fetch_officer_promise_performance,
)
from services.analytics_query import analytics_datetime_clause
from services.collections import (
    build_collections_page,
    collections_filters_to_query_params,
    group_collections_history,
    parse_collections_list_filters,
    persist_collections_update,
    validate_collections_form,
)
from services.collections_timeline import build_collections_activity_timeline
from services.delinquency import delinquency_context, enrich_collections_queue_row_with_intelligence
from services.loans import loan_servicing_summary
from services.notifications import (
    build_notifications_page,
    parse_notification_filters,
    persist_notification_acknowledgement,
)
from services.promise_recommendations import build_promise_recommendations
from services.promises import (
    group_promise_history,
    persist_promise_create,
    persist_promise_status_update,
    validate_promise_create_form,
    validate_promise_status_update,
)
from utils.auth import get_request_actor, require_admin_auth
from utils.csv_export import make_csv_response, make_streaming_csv_response
from utils.csrf import ensure_session_csrf_token, validate_csrf
from utils.errors import flash_operational_error
from utils.operational import log_admin_export
from utils.permissions import operator_has_permission, require_permission
from utils.collections_resilience import run_collections_operational_warnings
from services.filters import safe_return_url


def register_phase_routes(bp: Blueprint) -> None:
    """Attach recovered admin routes to the existing admin blueprint."""
    _register_notification_routes(bp)
    _register_collections_routes(bp)
    _register_promise_routes(bp)
    _register_export_routes(bp)


def _register_notification_routes(bp: Blueprint) -> None:
    @bp.route("/admin/notifications")
    @require_admin_auth
    @require_permission(PERM_VIEW_OPERATIONS)
    def admin_notifications():
        operator = g.operator
        filters = parse_notification_filters(request.args)

        conn = get_db_connection()
        cursor = conn.cursor()
        page_data = build_notifications_page(cursor, operator["id"], filters)
        conn.close()

        return render_template(
            "notifications.html",
            csrf_token=ensure_session_csrf_token(),
            active_nav="notifications",
            page_title="Operational Notifications",
            **page_data,
        )

    @bp.route("/admin/notifications/<int:notification_id>/acknowledge", methods=["POST"])
    @require_admin_auth
    @require_permission(PERM_VIEW_OPERATIONS)
    def admin_notification_acknowledge(notification_id: int):
        if not validate_csrf(request.form.get("csrf_token", "")):
            flash("Security check failed. Please try again.", "error")
            return redirect(url_for("admin_notifications"))

        operator = g.operator
        actor = get_request_actor()
        ok = persist_notification_acknowledgement(
            notification_id,
            operator["id"],
            acknowledged_by=actor,
        )
        if ok:
            flash("Notification acknowledged.", "success")
        else:
            flash("Notification was not found or is already acknowledged.", "info")
        return redirect(url_for("admin_notifications", filter=request.args.get("filter", "")))


def _register_collections_routes(bp: Blueprint) -> None:
    @bp.route("/admin/collections")
    @require_admin_auth
    @require_permission(PERM_VIEW_COLLECTIONS)
    def admin_collections():
        filters = parse_collections_list_filters(request.args)
        filter_query = collections_filters_to_query_params(filters)

        conn = get_db_connection()
        cursor = conn.cursor()
        queue_kpis = fetch_collections_queue_kpis(cursor)
        page_data = build_collections_page(cursor, filters)
        run_collections_operational_warnings(cursor)
        conn.close()

        return render_template(
            "collections.html",
            csrf_token=ensure_session_csrf_token(),
            active_nav="collections",
            page_title="Collections Operations",
            queue_kpis=queue_kpis,
            filters=filters,
            filter_query=filter_query,
            collections_statuses=COLLECTIONS_STATUSES,
            collections_priorities=COLLECTIONS_PRIORITIES,
            delinquency_buckets=DELINQUENCY_BUCKETS,
            promise_queue_filters=PROMISE_QUEUE_FILTERS,
            promise_queue_filter_labels=PROMISE_QUEUE_FILTER_LABELS,
            queue=page_data["queue"],
            total=page_data["total"],
            page=page_data["page"],
            total_pages=page_data["total_pages"],
            export_delinquent_url=url_for("admin_export_collections_delinquent"),
            export_recovery_summary_url=url_for("admin_export_collections_recovery_summary"),
            export_escalation_url=url_for("admin_export_collections_escalation_report"),
            export_officer_recovery_url=url_for("admin_export_collections_officer_recovery"),
            export_aging_url=url_for("admin_export_collections_aging_movement"),
            export_outcome_url=url_for("admin_export_collections_outcome_distribution"),
            export_workload_url=url_for("admin_export_collections_workload"),
            export_exposure_url=url_for("admin_export_collections_exposure"),
            export_active_promises_url=url_for("admin_export_promises_active"),
            export_broken_promises_url=url_for("admin_export_promises_broken"),
            export_overdue_promises_url=url_for("admin_export_promises_overdue"),
        )

    @bp.route("/admin/collections/<int:application_id>")
    @require_admin_auth
    @require_permission(PERM_VIEW_COLLECTIONS)
    def admin_collections_detail(application_id: int):
        application = fetch_application(application_id)
        if application is None:
            flash("Application not found.", "error")
            return redirect(url_for("admin_collections"))

        conn = get_db_connection()
        cursor = conn.cursor()
        intel_ctx = fetch_application_intelligence_context(cursor, [application_id]).get(application_id, {})
        promise_summary = fetch_promise_summary_for_application(cursor, application_id)
        intel_ctx["promise_summary"] = promise_summary
        account = enrich_collections_queue_row_with_intelligence(application, intel_ctx)
        history_rows = fetch_collections_history_rows(cursor, application_id)
        repayment_rows = fetch_repayment_rows(cursor, application_id)
        promise_history_rows = fetch_promise_history_rows(cursor, application_id)
        officers = fetch_distinct_officers(cursor)
        conn.close()

        active_promise = promise_summary.get("active_promise")
        repayments_after = 0.0
        if active_promise:
            conn = get_db_connection()
            cursor = conn.cursor()
            conversion_rows = fetch_repayment_conversion_rows(cursor, REPORT_EXPORT_MAX_ROWS)
            conn.close()
            for row in conversion_rows:
                if row["application_id"] == application_id and row["promise_id"] == active_promise["id"]:
                    repayments_after = float(row.get("repayments_after_promise") or 0)
                    break

        promise_recommendations = build_promise_recommendations(
            account,
            active_promise=active_promise,
            broken_count=promise_summary.get("broken_count", 0),
            fulfilled_count=promise_summary.get("fulfilled_count", 0),
            repayments_after_promise=repayments_after,
        )

        operator = g.operator
        return render_template(
            "collections_detail.html",
            application=application,
            account=account,
            loan_servicing_summary=loan_servicing_summary(application),
            delinquency=delinquency_context(application),
            repayment_history=repayment_rows,
            promise_summary=promise_summary,
            promise_history=group_promise_history(promise_history_rows),
            promise_recommendations=promise_recommendations,
            collections_history=group_collections_history(history_rows),
            activity_timeline=build_collections_activity_timeline(
                history_rows,
                repayment_rows=repayment_rows,
                promise_history_rows=promise_history_rows,
            ),
            officers=officers,
            can_mutate_collections=operator_has_permission(operator, PERM_MUTATE_COLLECTIONS),
            collections_statuses=COLLECTIONS_STATUSES,
            collections_priorities=COLLECTIONS_PRIORITIES,
            collections_risk_levels=COLLECTIONS_RISK_LEVELS,
            csrf_token=ensure_session_csrf_token(),
            application_detail_url=url_for("admin_application_detail", application_id=application_id),
            list_return_url=safe_return_url(request.args.get("return")),
            active_nav="collections",
            page_title=f"Collections — {application['business_name']}",
        )

    @bp.route("/admin/collections/<int:application_id>/update", methods=["POST"])
    @require_admin_auth
    @require_permission(PERM_MUTATE_COLLECTIONS, action="collections_update")
    def admin_collections_update(application_id: int):
        if not validate_csrf(request.form.get("csrf_token", "")):
            flash("Security check failed. Please try again.", "error")
            return redirect(url_for("admin_collections_detail", application_id=application_id))

        application = fetch_application(application_id)
        if application is None:
            flash("Application not found.", "error")
            return redirect(url_for("admin_collections"))

        snapshot, error, warnings = validate_collections_form(request.form, application)
        if error:
            category = "info" if error.startswith("No collections changes") else "error"
            flash(error, category)
            return redirect(url_for("admin_collections_detail", application_id=application_id))

        actor = get_request_actor()
        context_notes = (request.form.get("collections_context") or "").strip()[:1000]
        try:
            persist_collections_update(
                application_id,
                application,
                snapshot,
                actor,
                context_notes=context_notes,
            )
        except Exception:
            flash_operational_error()
            return redirect(url_for("admin_collections_detail", application_id=application_id))

        flash_message = f"Collections record saved for application #{application_id}."
        for warning in warnings:
            flash_message += f" {warning}"
        flash(flash_message, "success")
        return redirect(url_for("admin_collections_detail", application_id=application_id))


def _register_promise_routes(bp: Blueprint) -> None:
    @bp.route("/admin/collections/<int:application_id>/promises", methods=["POST"])
    @require_admin_auth
    @require_permission(PERM_MUTATE_COLLECTIONS, action="promise_create")
    def admin_collections_promise_create(application_id: int):
        if not validate_csrf(request.form.get("csrf_token", "")):
            flash("Security check failed. Please try again.", "error")
            return redirect(url_for("admin_collections_detail", application_id=application_id))

        application = fetch_application(application_id)
        if application is None:
            flash("Application not found.", "error")
            return redirect(url_for("admin_collections"))

        snapshot, error = validate_promise_create_form(request.form, application)
        if error:
            flash(error, "error")
            return redirect(url_for("admin_collections_detail", application_id=application_id))

        actor = get_request_actor()
        context_notes = (request.form.get("promise_context") or "").strip()[:1000]
        try:
            persist_promise_create(application_id, snapshot, actor, context_notes=context_notes)
        except Exception:
            flash_operational_error()
            return redirect(url_for("admin_collections_detail", application_id=application_id))

        flash(f"Recovery promise recorded for application #{application_id}.", "success")
        return redirect(url_for("admin_collections_detail", application_id=application_id))

    @bp.route(
        "/admin/collections/<int:application_id>/promises/<int:promise_id>/status",
        methods=["POST"],
    )
    @require_admin_auth
    @require_permission(PERM_MUTATE_COLLECTIONS, action="promise_status")
    def admin_collections_promise_status(application_id: int, promise_id: int):
        if not validate_csrf(request.form.get("csrf_token", "")):
            flash("Security check failed. Please try again.", "error")
            return redirect(url_for("admin_collections_detail", application_id=application_id))

        conn = get_db_connection()
        cursor = conn.cursor()
        promise = fetch_promise_by_id(cursor, promise_id)
        conn.close()
        if promise is None or promise["application_id"] != application_id:
            flash("Promise not found.", "error")
            return redirect(url_for("admin_collections_detail", application_id=application_id))

        snapshot, error, warnings = validate_promise_status_update(request.form, promise)
        if error:
            category = "info" if "No promise status change" in error else "error"
            flash(error, category)
            return redirect(url_for("admin_collections_detail", application_id=application_id))

        actor = get_request_actor()
        context_notes = (request.form.get("promise_context") or "").strip()[:1000]
        try:
            persist_promise_status_update(
                promise_id,
                promise,
                snapshot,
                actor,
                context_notes=context_notes,
            )
        except Exception:
            flash_operational_error()
            return redirect(url_for("admin_collections_detail", application_id=application_id))

        flash_message = f"Promise status updated for application #{application_id}."
        for warning in warnings:
            flash_message += f" {warning}"
        flash(flash_message, "success")
        return redirect(url_for("admin_collections_detail", application_id=application_id))


def _register_export_routes(bp: Blueprint) -> None:
    @bp.route("/admin/export/collections/delinquent")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_collections_delinquent")
    def admin_export_collections_delinquent():
        filters = parse_collections_list_filters(request.args)
        filename = "collections_delinquent.csv"

        conn = get_db_connection()
        cursor = conn.cursor()

        def row_iter():
            try:
                for row in iter_collections_queue_for_export(cursor, filters):
                    yield row
            finally:
                conn.close()

        log_admin_export("collections_delinquent", filename=filename)
        return make_streaming_csv_response(
            filename,
            COLLECTIONS_DELINQUENT_EXPORT_COLUMNS,
            row_iter(),
        )

    @bp.route("/admin/export/collections/recovery-summary")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_collections_recovery_summary")
    def admin_export_collections_recovery_summary():
        filename = "collections_recovery_summary.csv"
        conn = get_db_connection()
        cursor = conn.cursor()

        def row_iter():
            try:
                for row in iter_collections_recovery_summary_export(cursor):
                    yield row
            finally:
                conn.close()

        log_admin_export("collections_recovery_summary", filename=filename)
        return make_streaming_csv_response(
            filename,
            COLLECTIONS_RECOVERY_SUMMARY_EXPORT_COLUMNS,
            row_iter(),
        )

    @bp.route("/admin/export/collections/activity")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_collections_activity")
    def admin_export_collections_activity():
        from utils.time_range import parse_analytics_range

        range_key = parse_analytics_range(request.args)
        range_clause, range_params = analytics_datetime_clause(range_key, "ch.created_at")
        filename = f"collections_activity_{range_key}.csv"

        conn = get_db_connection()
        cursor = conn.cursor()
        rows = fetch_collections_activity_for_export(
            cursor,
            range_clause,
            range_params,
            REPORT_EXPORT_MAX_ROWS,
        )
        conn.close()

        log_admin_export(
            "collections_activity",
            filename=filename,
            range_key=range_key,
            row_count=len(rows),
        )
        return make_csv_response(filename, COLLECTIONS_ACTIVITY_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/collections/workload")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_collections_workload")
    def admin_export_collections_workload():
        filename = "collections_workload.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = fetch_collections_officer_workload(cursor)
        conn.close()
        log_admin_export("collections_workload", filename=filename, row_count=len(rows))
        return make_csv_response(filename, COLLECTIONS_WORKLOAD_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/collections/exposure")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_collections_exposure")
    def admin_export_collections_exposure():
        filename = "collections_exposure.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = fetch_collections_delinquency_distribution(cursor)
        conn.close()
        log_admin_export("collections_exposure", filename=filename, row_count=len(rows))
        return make_csv_response(filename, COLLECTIONS_EXPOSURE_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/collections/escalation-report")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_collections_escalation")
    def admin_export_collections_escalation_report():
        filename = "collections_escalation_report.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = fetch_escalation_report_rows(cursor, REPORT_EXPORT_MAX_ROWS)
        conn.close()
        log_admin_export("collections_escalation", filename=filename, row_count=len(rows))
        return make_csv_response(filename, COLLECTIONS_ESCALATION_REPORT_COLUMNS, rows)

    @bp.route("/admin/export/collections/officer-recovery")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_collections_officer_recovery")
    def admin_export_collections_officer_recovery():
        filename = "collections_officer_recovery.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = fetch_officer_recovery_performance(cursor)
        conn.close()
        log_admin_export("collections_officer_recovery", filename=filename, row_count=len(rows))
        return make_csv_response(filename, COLLECTIONS_OFFICER_RECOVERY_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/collections/aging-movement")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_collections_aging")
    def admin_export_collections_aging_movement():
        filename = "collections_aging_movement.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = fetch_collections_delinquency_distribution(cursor)
        conn.close()
        log_admin_export("collections_aging", filename=filename, row_count=len(rows))
        return make_csv_response(filename, COLLECTIONS_EXPOSURE_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/collections/outcome-distribution")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_collections_outcome")
    def admin_export_collections_outcome_distribution():
        filename = "collections_outcome_distribution.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = fetch_recovery_outcome_distribution(cursor)
        conn.close()
        log_admin_export("collections_outcome", filename=filename, row_count=len(rows))
        return make_csv_response(filename, COLLECTIONS_OUTCOME_DISTRIBUTION_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/promises/active")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_promises_active")
    def admin_export_promises_active():
        filename = "promises_active.csv"
        conn = get_db_connection()
        cursor = conn.cursor()

        def row_iter():
            try:
                for row in iter_active_promises_export(cursor):
                    yield row
            finally:
                conn.close()

        log_admin_export("promises_active", filename=filename)
        return make_streaming_csv_response(filename, PROMISES_ACTIVE_EXPORT_COLUMNS, row_iter())

    @bp.route("/admin/export/promises/broken")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_promises_broken")
    def admin_export_promises_broken():
        filename = "promises_broken.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = fetch_broken_commitments_export(cursor, REPORT_EXPORT_MAX_ROWS)
        conn.close()
        log_admin_export("promises_broken", filename=filename, row_count=len(rows))
        return make_csv_response(filename, PROMISES_BROKEN_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/promises/overdue")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_promises_overdue")
    def admin_export_promises_overdue():
        filename = "promises_overdue.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = fetch_overdue_commitments_export(cursor, REPORT_EXPORT_MAX_ROWS)
        conn.close()
        log_admin_export("promises_overdue", filename=filename, row_count=len(rows))
        return make_csv_response(filename, PROMISES_OVERDUE_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/promises/officer-performance")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_promises_officer_performance")
    def admin_export_promises_officer_performance():
        filename = "promises_officer_performance.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = fetch_officer_promise_performance(cursor)
        conn.close()
        log_admin_export("promises_officer_performance", filename=filename, row_count=len(rows))
        return make_csv_response(filename, PROMISES_OFFICER_PERFORMANCE_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/promises/repayment-conversion")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_promises_repayment_conversion")
    def admin_export_promises_repayment_conversion():
        filename = "promises_repayment_conversion.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = fetch_repayment_conversion_rows(cursor, REPORT_EXPORT_MAX_ROWS)
        conn.close()
        log_admin_export("promises_repayment_conversion", filename=filename, row_count=len(rows))
        return make_csv_response(filename, PROMISES_REPAYMENT_CONVERSION_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/notifications/alerts")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_notifications_alerts")
    def admin_export_notifications_alerts():
        filename = "notifications_alerts.csv"
        conn = get_db_connection()
        cursor = conn.cursor()

        def row_iter():
            try:
                for row in iter_operational_alerts_export(cursor):
                    yield dict(row)
            finally:
                conn.close()

        log_admin_export("notifications_alerts", filename=filename)
        return make_streaming_csv_response(filename, NOTIFICATIONS_ALERTS_EXPORT_COLUMNS, row_iter())

    @bp.route("/admin/export/notifications/unresolved")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_notifications_unresolved")
    def admin_export_notifications_unresolved():
        filename = "notifications_unresolved.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = [dict(row) for row in fetch_unresolved_notifications_export(cursor, REPORT_EXPORT_MAX_ROWS)]
        conn.close()
        log_admin_export("notifications_unresolved", filename=filename, row_count=len(rows))
        return make_csv_response(filename, NOTIFICATIONS_UNRESOLVED_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/notifications/governance")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_notifications_governance")
    def admin_export_notifications_governance():
        filename = "notifications_governance.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = [dict(row) for row in fetch_governance_alerts_export(cursor, REPORT_EXPORT_MAX_ROWS)]
        conn.close()
        log_admin_export("notifications_governance", filename=filename, row_count=len(rows))
        return make_csv_response(filename, NOTIFICATIONS_GOVERNANCE_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/notifications/ack-metrics")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_notifications_ack_metrics")
    def admin_export_notifications_ack_metrics():
        filename = "notifications_ack_metrics.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = fetch_operator_acknowledgement_metrics_export(cursor)
        conn.close()
        log_admin_export("notifications_ack_metrics", filename=filename, row_count=len(rows))
        return make_csv_response(filename, NOTIFICATIONS_ACK_METRICS_EXPORT_COLUMNS, rows)

    @bp.route("/admin/export/notifications/critical-events")
    @require_admin_auth
    @require_permission(PERM_EXPORT, action="export_notifications_critical_events")
    def admin_export_notifications_critical_events():
        filename = "notifications_critical_events.csv"
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = [dict(row) for row in fetch_critical_event_summary_export(cursor, REPORT_EXPORT_MAX_ROWS)]
        conn.close()
        log_admin_export("notifications_critical_events", filename=filename, row_count=len(rows))
        return make_csv_response(filename, NOTIFICATIONS_CRITICAL_EVENTS_EXPORT_COLUMNS, rows)
