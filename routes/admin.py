from flask import Blueprint, Response, flash, g, redirect, render_template, request, url_for

from constants.analytics import ANALYTICS_TIME_RANGES
from constants.reporting import (
    APPLICATION_EXPORT_COLUMNS,
    AUDIT_EXPORT_COLUMNS,
    REPORT_EXPORT_MAX_ROWS,
    REPORT_EXPORT_TYPES,
)
from constants.loans import (
    LOAN_LIFECYCLE_STATUS_LABELS,
    LOAN_LIFECYCLE_STATUSES,
    REPAYMENT_FREQUENCIES,
    REPAYMENT_RISK_LEVELS,
)
from constants.underwriting import (
    UNDERWRITING_ASSESSMENT_FIELD_LABELS,
    UNDERWRITING_ASSESSMENT_LABELS,
    UNDERWRITING_ASSESSMENT_RATINGS,
    UNDERWRITING_STATUS_LABELS,
    UNDERWRITING_STATUSES,
)
from constants.workflow import (
    ADMIN_FILTER_PRESETS,
    ADMIN_PAGE_SIZE,
    APPLICATION_RISK_LEVELS,
    APPLICATION_STATUSES,
    APPLICATION_SUB_STATUSES,
    KPI_ACTIVE_PIPELINE_STATUSES,
)
from repositories.applications import (
    fetch_application,
    fetch_application_kpis,
    fetch_applications_for_export,
    fetch_attention_applications,
    fetch_executive_kpis,
    fetch_officer_workload,
    fetch_pipeline_backlog,
    fetch_recent_applications,
    fetch_risk_distribution,
    fetch_status_distribution,
)
from repositories.audit import fetch_audit_history_for_export, fetch_workflow_history_rows
from repositories.database import get_db_connection
from repositories.loans import (
    fetch_loan_account_history_rows,
    fetch_loan_lifecycle_distribution,
    fetch_repayment_rows,
    fetch_repayments_for_export,
)
from repositories.underwriting import (
    fetch_underwriting_decision_history,
    fetch_underwriting_portfolio_distribution,
)
from repositories.officers import (
    fetch_distinct_officers,
    fetch_registered_officers,
    resolve_officer_name,
)
from services.analytics import (
    analytics_insights,
    fetch_analytics_activity_summary,
    fetch_analytics_backlog_snapshot,
    fetch_analytics_distribution,
    fetch_analytics_fraud_trend,
    fetch_analytics_intake_trend,
    fetch_analytics_officer_workload,
    fetch_analytics_outcome_trend,
    fetch_analytics_period_kpis,
    fetch_analytics_pipeline_distribution,
)
from services.audit import (
    group_workflow_history_batches,
    is_risky_status_transition_warning,
    persist_workflow_update,
    requires_audit_context,
    validate_audit_context,
    workflow_snapshot_from_row,
    workflow_snapshot_from_workflow,
)
from services.filters import (
    active_filter_chips,
    build_applications_where,
    filters_have_constraints,
    filters_to_query_params,
    parse_admin_list_filters,
    safe_return_url,
)
from services.overview import overview_drilldown_links
from services.portfolio_intelligence import build_portfolio_intelligence_package, portfolio_export_metric_rows
from services.reporting import build_reports_page_data, report_export_urls
from services.loans import (
    delinquency_context,
    group_loan_account_history,
    loan_servicing_summary,
    persist_loan_account_update,
    persist_repayment,
    validate_loan_account_form,
    validate_repayment_form,
)
from services.underwriting import (
    financing_rationale_summary,
    group_underwriting_decision_history,
    persist_underwriting_update,
    validate_underwriting_form,
)
from services.workflow import (
    apply_workflow_quick_action,
    application_needs_attention,
    next_pipeline_status,
    validate_workflow_form,
)
from utils.auth import get_request_actor, require_admin_auth
from utils.csv_export import distribution_export_rows, make_csv_response, make_sectioned_csv_response
from utils.csrf import ensure_session_csrf_token, validate_csrf
from utils.errors import flash_operational_error
from utils.operational import log_admin_export
from utils.ops_logging import (
    log_db_retrieval_count,
    log_dashboard_query_failed,
    log_dashboard_query_result,
    log_workflow_failure,
)
from utils.time_range import parse_analytics_range

bp = Blueprint("admin", __name__)

@bp.route("/admin/overview")
@require_admin_auth
def admin_overview():
    conn = get_db_connection()
    cursor = conn.cursor()

    kpis = fetch_executive_kpis(cursor)
    status_distribution = fetch_status_distribution(cursor)
    risk_distribution = fetch_risk_distribution(cursor)
    pipeline_backlog = fetch_pipeline_backlog(cursor)
    officer_workload = fetch_officer_workload(cursor)
    recent_applications = fetch_recent_applications(cursor)
    attention_applications = fetch_attention_applications(cursor)
    portfolio = build_portfolio_intelligence_package(cursor, "30d")

    conn.close()

    total_for_bars = kpis["total_applications"] or 1
    for item in status_distribution:
        item["share"] = round((item["count"] / total_for_bars) * 100, 1)
    for item in risk_distribution:
        item["share"] = round((item["count"] / total_for_bars) * 100, 1)

    pipeline_total = sum(item["count"] for item in pipeline_backlog)
    pipeline_denominator = pipeline_total or 1
    for item in pipeline_backlog:
        item["share"] = round((item["count"] / pipeline_denominator) * 100, 1)

    log_dashboard_query_result(
        "Admin overview query results",
        total_applications=kpis.get("total_applications", 0),
        status_distribution=len(status_distribution),
        risk_distribution=len(risk_distribution),
        pipeline_backlog_total=pipeline_total,
        recent_count=len(recent_applications),
        attention_count=len(attention_applications),
    )

    return render_template(
        "overview.html",
        kpis=kpis,
        kpi_links=overview_drilldown_links(),
        status_distribution=status_distribution,
        risk_distribution=risk_distribution,
        pipeline_backlog=pipeline_backlog,
        pipeline_total=pipeline_total,
        officer_workload=officer_workload,
        recent_applications=recent_applications,
        attention_applications=attention_applications,
        active_nav="overview",
        page_title="Operations Overview",
        portfolio_empty=kpis["total_applications"] == 0,
        portfolio=portfolio,
        range_label="Last 30 days",
        show_repayment_trend=True,
    )


@bp.route("/admin/analytics")
@require_admin_auth
def admin_analytics():
    range_key = parse_analytics_range(request.args)

    conn = get_db_connection()
    cursor = conn.cursor()

    period_kpis = fetch_analytics_period_kpis(cursor, range_key)
    intake_trend = fetch_analytics_intake_trend(cursor, range_key)
    fraud_trend = fetch_analytics_fraud_trend(cursor, range_key)
    outcome_trend = fetch_analytics_outcome_trend(cursor, range_key)
    status_distribution = fetch_analytics_distribution(
        cursor, range_key, group_column="status", order_values=APPLICATION_STATUSES
    )
    risk_distribution = fetch_analytics_distribution(
        cursor, range_key, group_column="risk_level", order_values=APPLICATION_RISK_LEVELS
    )
    pipeline_distribution = fetch_analytics_pipeline_distribution(cursor, range_key)
    officer_workload = fetch_analytics_officer_workload(cursor, range_key)
    backlog = fetch_analytics_backlog_snapshot(cursor)
    activity_summary = fetch_analytics_activity_summary(cursor, range_key)
    underwriting_portfolio = fetch_underwriting_portfolio_distribution(cursor)
    underwriting_total = sum(item["count"] for item in underwriting_portfolio) or 1
    for item in underwriting_portfolio:
        item["share"] = round((item["count"] / underwriting_total) * 100, 1)

    loan_lifecycle_portfolio = fetch_loan_lifecycle_distribution(cursor)
    loan_total = sum(item["count"] for item in loan_lifecycle_portfolio) or 1
    for item in loan_lifecycle_portfolio:
        item["share"] = round((item["count"] / loan_total) * 100, 1)

    portfolio = build_portfolio_intelligence_package(cursor, range_key)

    conn.close()

    insights = analytics_insights(period_kpis, backlog, officer_workload, pipeline_distribution)
    insights = (portfolio["insights"] + insights)[:8]

    log_dashboard_query_result(
        "Admin analytics query results",
        range_key=range_key,
        total_applications=period_kpis.get("total_applications", 0),
        intake_points=len(intake_trend),
        fraud_points=len(fraud_trend),
        outcome_points=len(outcome_trend),
        status_distribution=len(status_distribution),
        risk_distribution=len(risk_distribution),
        pipeline_cases=len(pipeline_distribution),
        officer_workload=len(officer_workload),
        backlog_total=backlog.get("pipeline_total", 0),
    )

    return render_template(
        "analytics.html",
        range_key=range_key,
        range_label=ANALYTICS_TIME_RANGES[range_key],
        time_ranges=ANALYTICS_TIME_RANGES,
        export_urls=report_export_urls(range_key),
        period_kpis=period_kpis,
        intake_trend=intake_trend,
        fraud_trend=fraud_trend,
        outcome_trend=outcome_trend,
        status_distribution=status_distribution,
        risk_distribution=risk_distribution,
        pipeline_distribution=pipeline_distribution,
        officer_workload=officer_workload,
        backlog=backlog,
        activity_summary=activity_summary,
        underwriting_portfolio=underwriting_portfolio,
        loan_lifecycle_portfolio=loan_lifecycle_portfolio,
        insights=insights,
        portfolio=portfolio,
        show_repayment_trend=True,
        active_nav="analytics",
        page_title="Operational Analytics",
        portfolio_empty=period_kpis["total_applications"] == 0,
    )


@bp.route("/admin/reports")
@require_admin_auth
def admin_reports():
    range_key = parse_analytics_range(request.args)

    conn = get_db_connection()
    cursor = conn.cursor()
    report_data = build_reports_page_data(cursor, range_key)
    conn.close()

    return render_template(
        "reports.html",
        active_nav="reports",
        page_title="Operational Reports",
        range_key=range_key,
        range_label=ANALYTICS_TIME_RANGES[range_key],
        time_ranges=ANALYTICS_TIME_RANGES,
        export_urls=report_export_urls(range_key),
        portfolio_empty=report_data["portfolio_kpis"]["total_applications"] == 0,
        show_repayment_trend=True,
        **report_data,
    )


@bp.route("/admin/export/applications")
@require_admin_auth
def admin_export_applications():
    filters = parse_admin_list_filters(request.args)
    where_sql, where_params = build_applications_where(filters)

    conn = get_db_connection()
    cursor = conn.cursor()
    rows = fetch_applications_for_export(cursor, where_sql, where_params)
    conn.close()

    suffix = "filtered" if filters_have_constraints(filters) else "all"
    filename = f"applications_{suffix}.csv"
    log_admin_export("applications", filename=filename, row_count=len(rows), filtered=suffix == "filtered")
    return make_csv_response(filename, APPLICATION_EXPORT_COLUMNS, rows)


@bp.route("/admin/export/audit")
@require_admin_auth
def admin_export_audit():
    range_key = parse_analytics_range(request.args)
    application_id = None
    raw_id = (request.args.get("application_id") or "").strip()
    if raw_id.isdigit():
        application_id = int(raw_id)

    conn = get_db_connection()
    cursor = conn.cursor()
    rows = fetch_audit_history_for_export(cursor, range_key, application_id)
    conn.close()

    filename = f"audit_history_{range_key}"
    if application_id is not None:
        filename += f"_app_{application_id}"
    csv_name = f"{filename}.csv"
    log_admin_export(
        "audit",
        filename=csv_name,
        row_count=len(rows),
        range_key=range_key,
        application_id=application_id,
    )
    return make_csv_response(csv_name, AUDIT_EXPORT_COLUMNS, rows)


@bp.route("/admin/export/report/<report_type>")
@require_admin_auth
def admin_export_report(report_type: str):
    if report_type not in REPORT_EXPORT_TYPES:
        return Response("Unknown report type.", status=404)

    range_key = parse_analytics_range(request.args)
    conn = get_db_connection()
    cursor = conn.cursor()
    data = build_reports_page_data(cursor, range_key)
    conn.close()

    dist_columns = (("label", "label"), ("count", "count"), ("share_pct", "share_pct"))
    metric_columns = (("metric", "metric"), ("value", "value"))

    if report_type == "pipeline":
        rows = distribution_export_rows(data["pipeline_distribution"])
        filename = f"pipeline_summary_{range_key}.csv"
        log_admin_export("report_pipeline", filename=filename, range_key=range_key, row_count=len(rows))
        return make_csv_response(filename, dist_columns, rows)

    if report_type == "risk":
        sections = [
            ("Period risk (created in range)", dist_columns, distribution_export_rows(data["risk_distribution"])),
            ("Portfolio risk (live)", dist_columns, distribution_export_rows(data["portfolio_risk"])),
        ]
        filename = f"risk_exposure_{range_key}.csv"
        log_admin_export("report_risk", filename=filename, range_key=range_key)
        return make_sectioned_csv_response(filename, sections)

    if report_type == "outcomes":
        outcome = data["outcome_summary"]
        rows = [
            {"metric": "Portfolio — active pipeline", "value": outcome["portfolio_pipeline"]},
            {"metric": "Portfolio — approved", "value": outcome["portfolio_approved"]},
            {"metric": "Portfolio — rejected", "value": outcome["portfolio_rejected"]},
            {"metric": f"Period ({range_key}) — applications created", "value": outcome["period_total"]},
            {"metric": f"Period ({range_key}) — approved-stage created", "value": outcome["period_approved"]},
            {"metric": f"Period ({range_key}) — rejected created", "value": outcome["period_rejected"]},
            {"metric": f"Period ({range_key}) — rejection rate %", "value": outcome["period_rejection_rate"]},
        ]
        status_rows = distribution_export_rows(data["status_distribution"])
        sections = [
            ("Approval and rejection summary", metric_columns, rows),
            ("Period status distribution", dist_columns, status_rows),
        ]
        filename = f"approval_outcomes_{range_key}.csv"
        log_admin_export("report_outcomes", filename=filename, range_key=range_key)
        return make_sectioned_csv_response(filename, sections)

    if report_type == "fraud":
        fraud = data["fraud_summary"]
        summary_rows = [
            {"metric": "Fraud-flagged (portfolio)", "value": fraud["fraud_flagged_total"]},
            {"metric": "Fraud-flagged in active pipeline", "value": fraud["fraud_in_pipeline"]},
            {"metric": f"Fraud-flagged created in period ({range_key})", "value": data["period_kpis"]["fraud_flagged"]},
        ]
        conn = get_db_connection()
        cursor = conn.cursor()
        fraud_apps = fetch_applications_for_export(
            cursor,
            " WHERE flagged_fraud = 1",
            [],
        )
        conn.close()
        sections = [
            ("Fraud review summary", metric_columns, summary_rows),
            ("Fraud-flagged applications", APPLICATION_EXPORT_COLUMNS, fraud_apps),
        ]
        filename = f"fraud_review_{range_key}.csv"
        log_admin_export("report_fraud", filename=filename, range_key=range_key, row_count=len(fraud_apps))
        return make_sectioned_csv_response(filename, sections)

    if report_type == "officers":
        rows = [
            {
                "officer": item["officer"],
                "total_count": item["total_count"],
                "pipeline_count": item["pipeline_count"],
                "fraud_count": item["fraud_count"],
                "load_share_pct": item.get("load_share", ""),
            }
            for item in data["officer_workload"]
        ]
        officer_columns = (
            ("officer", "officer"),
            ("total_count", "total_count"),
            ("pipeline_count", "pipeline_count"),
            ("fraud_count", "fraud_count"),
            ("load_share_pct", "load_share_pct"),
        )
        filename = f"officer_workload_{range_key}.csv"
        log_admin_export("report_officers", filename=filename, range_key=range_key, row_count=len(rows))
        return make_csv_response(filename, officer_columns, rows)

    if report_type == "portfolio":
        portfolio = data["portfolio_intelligence"]
        metric_columns = (("metric", "metric"), ("value", "value"))
        metric_rows = portfolio_export_metric_rows(
            portfolio["financial"],
            portfolio["underwriting_outcomes"],
            portfolio["throughput"],
        )
        aging_columns = (
            ("label", "label"),
            ("count", "count"),
            ("exposure", "exposure"),
            ("share_pct", "share"),
        )
        aging_rows = [
            {
                "label": item["label"],
                "count": item["count"],
                "exposure": item["exposure"],
                "share_pct": item.get("share", ""),
            }
            for item in portfolio["aging"]
        ]
        collections_columns = (
            ("officer", "officer"),
            ("collections_cases", "collections_cases"),
            ("exposure", "exposure"),
        )
        sections = [
            ("Portfolio financial metrics", metric_columns, metric_rows),
            ("Portfolio aging", aging_columns, aging_rows),
            (
                "Collections workload",
                collections_columns,
                portfolio["collections_workload"],
            ),
        ]
        filename = f"portfolio_intelligence_{range_key}.csv"
        log_admin_export("report_portfolio", filename=filename, range_key=range_key)
        return make_sectioned_csv_response(filename, sections)

    if report_type == "backlog":
        rows = distribution_export_rows(data["backlog"]["pipeline_backlog"])
        summary_rows = [
            {"metric": "Live pipeline backlog total", "value": data["backlog"]["pipeline_total"]},
            {"metric": "Bottleneck stage", "value": data["backlog"]["bottleneck_stage"] or "—"},
            {"metric": "Bottleneck count", "value": data["backlog"]["bottleneck_count"]},
        ]
        sections = [
            ("Backlog summary", metric_columns, summary_rows),
            ("Pipeline stage backlog", dist_columns, rows),
        ]
        filename = f"operational_backlog_{range_key}.csv"
        log_admin_export("report_backlog", filename=filename, range_key=range_key)
        return make_sectioned_csv_response(filename, sections)

    # operational — bundled executive export
    gov = data["governance"]
    executive_rows = [{"summary": line} for line in data["executive_lines"]]
    governance_rows = [
        {"metric": "Workflow batches in period", "value": gov["workflow_batches"]},
        {"metric": "Audit events in period", "value": gov["total_events"]},
        {"metric": "Critical audit events", "value": gov["critical_events"]},
        {"metric": "Unique operators", "value": gov["unique_operators"]},
        {"metric": "Applications with audit activity", "value": gov["applications_touched"]},
        {"metric": "Workflow updates (distinct batches)", "value": data["activity_summary"]["updates_in_period"]},
    ]
    sections = [
        ("Executive summary", (("summary", "summary"),), executive_rows),
        ("Governance and audit", metric_columns, governance_rows),
        ("Pipeline distribution (period)", dist_columns, distribution_export_rows(data["pipeline_distribution"])),
        (
            "Officer workload (period)",
            (
                ("officer", "officer"),
                ("pipeline_count", "pipeline_count"),
                ("total_count", "total_count"),
            ),
            [
                {
                    "officer": item["officer"],
                    "pipeline_count": item["pipeline_count"],
                    "total_count": item["total_count"],
                }
                for item in data["officer_workload"]
            ],
        ),
    ]
    filename = f"operational_report_{range_key}.csv"
    log_admin_export("report_operational", filename=filename, range_key=range_key)
    return make_sectioned_csv_response(filename, sections)


@bp.route('/admin')
@require_admin_auth
def admin():
    filters = parse_admin_list_filters(request.args)
    where_sql, where_params = build_applications_where(filters)

    conn = get_db_connection()
    cursor = conn.cursor()

    kpis = fetch_application_kpis(cursor)
    officers = fetch_distinct_officers(cursor)

    cursor.execute(f"SELECT COUNT(*) AS total FROM applications{where_sql}", where_params)
    total_matching = cursor.fetchone()["total"] or 0

    total_pages = max(1, (total_matching + ADMIN_PAGE_SIZE - 1) // ADMIN_PAGE_SIZE)
    page = min(filters["page"], total_pages)
    offset = (page - 1) * ADMIN_PAGE_SIZE

    cursor.execute(
        f"""
        SELECT
            id,
            business_name,
            owner_name,
            email,
            revenue,
            product,
            status,
            sub_status,
            risk_level,
            flagged_fraud,
            assigned_officer,
            underwriting_status,
            loan_lifecycle_status,
            outstanding_balance,
            due_date,
            repayment_risk_level
        FROM applications
        {where_sql}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (*where_params, ADMIN_PAGE_SIZE, offset),
    )
    applications = cursor.fetchall()
    conn.close()

    log_db_retrieval_count(
        "Admin applications list query results",
        preset=filters.get("preset", ""),
        filters_active=filters_have_constraints(filters),
        page=page,
        page_size=ADMIN_PAGE_SIZE,
        fetched_count=len(applications),
        total_matching=total_matching,
    )

    pagination = {
        "page": page,
        "total_pages": total_pages,
        "total_matching": total_matching,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "page_size": ADMIN_PAGE_SIZE,
    }

    preset = filters.get("preset") or ""
    filter_preset_label = ADMIN_FILTER_PRESETS.get(preset, "")
    if not filter_preset_label and filters.get("flagged_fraud") == "1":
        filter_preset_label = "Fraud-flagged applications"

    portfolio_empty = kpis["total_applications"] == 0
    filters_active = filters_have_constraints(filters)

    filter_query = filters_to_query_params(filters)

    return render_template(
        "dashboard.html",
        applications=applications,
        filters=filters,
        kpis=kpis,
        kpi_links=overview_drilldown_links(),
        pagination=pagination,
        filter_query=filter_query,
        export_applications_url=url_for("admin_export_applications", **filter_query),
        filter_preset_label=filter_preset_label,
        active_filter_chips=active_filter_chips(filters),
        filters_active=filters_active,
        portfolio_empty=portfolio_empty,
        statuses=APPLICATION_STATUSES,
        sub_statuses=APPLICATION_SUB_STATUSES,
        risk_levels=APPLICATION_RISK_LEVELS,
        loan_lifecycle_statuses=LOAN_LIFECYCLE_STATUSES,
        officers=officers,
        active_nav="applications",
        page_title="Applications",
    )


@bp.route("/admin/applications/<int:application_id>")
@require_admin_auth
def admin_application_detail(application_id: int):
    application = fetch_application(application_id)
    if application is None:
        return Response("Application not found.", status=404)

    conn = get_db_connection()
    cursor = conn.cursor()
    history_rows = fetch_workflow_history_rows(cursor, application_id)
    underwriting_rows = fetch_underwriting_decision_history(cursor, application_id)
    loan_history_rows = fetch_loan_account_history_rows(cursor, application_id)
    repayment_rows = fetch_repayment_rows(cursor, application_id)
    officers = fetch_registered_officers(cursor)
    conn.close()

    csrf_token = ensure_session_csrf_token()
    next_status = next_pipeline_status(application["status"])
    status_transition_hint = is_risky_status_transition_warning(
        application["status"],
        next_status or application["status"],
    )
    return render_template(
        "application_detail.html",
        application=application,
        csrf_token=csrf_token,
        statuses=APPLICATION_STATUSES,
        sub_statuses=APPLICATION_SUB_STATUSES,
        risk_levels=APPLICATION_RISK_LEVELS,
        officers=officers,
        next_pipeline_status=next_status,
        needs_attention=application_needs_attention(application),
        timeline_batches=group_workflow_history_batches(history_rows),
        underwriting_history=group_underwriting_decision_history(underwriting_rows),
        underwriting_statuses=UNDERWRITING_STATUSES,
        underwriting_status_labels=UNDERWRITING_STATUS_LABELS,
        underwriting_assessment_ratings=UNDERWRITING_ASSESSMENT_RATINGS,
        underwriting_assessment_labels=UNDERWRITING_ASSESSMENT_LABELS,
        underwriting_assessment_field_labels=UNDERWRITING_ASSESSMENT_FIELD_LABELS,
        financing_rationale=financing_rationale_summary(application),
        loan_servicing_summary=loan_servicing_summary(application),
        delinquency=delinquency_context(application),
        loan_account_history=group_loan_account_history(loan_history_rows),
        repayment_history=repayment_rows,
        loan_lifecycle_statuses=LOAN_LIFECYCLE_STATUSES,
        loan_lifecycle_status_labels=LOAN_LIFECYCLE_STATUS_LABELS,
        repayment_frequencies=REPAYMENT_FREQUENCIES,
        repayment_risk_levels=REPAYMENT_RISK_LEVELS,
        admin_actor=getattr(g, "admin_actor", get_request_actor()),
        status_transition_hint=status_transition_hint,
        export_audit_url=url_for(
            "admin_export_audit",
            application_id=application_id,
            range="all",
        ),
        active_nav="applications",
        page_title=f"Application #{application_id}",
        list_return_url=safe_return_url(request.args.get("return")),
    )


@bp.route("/admin/applications/<int:application_id>/underwriting", methods=["POST"])
@require_admin_auth
def admin_application_underwriting(application_id: int):
    if not validate_csrf(request.form.get("csrf_token", "")):
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("admin_application_detail", application_id=application_id))

    application = fetch_application(application_id)
    if application is None:
        return Response("Application not found.", status=404)

    actor = getattr(g, "admin_actor", get_request_actor())
    form_payload = request.form.to_dict()
    form_payload["reviewed_by"] = actor

    snapshot, validation_error = validate_underwriting_form(form_payload, application)
    if validation_error:
        category = "info" if validation_error.startswith("No underwriting changes") else "error"
        flash(validation_error, category)
        return redirect(url_for("admin_application_detail", application_id=application_id))

    context_notes = (request.form.get("underwriting_context") or "").strip()[:1000]

    try:
        persist_underwriting_update(
            application_id,
            application,
            snapshot,
            actor,
            context_notes=context_notes,
        )
    except Exception as exc:
        log_workflow_failure(
            "Underwriting update could not be saved",
            application_id=application_id,
            actor=actor,
            error=str(exc),
        )
        flash_operational_error()
        return redirect(url_for("admin_application_detail", application_id=application_id))

    status_label = UNDERWRITING_STATUS_LABELS.get(snapshot["underwriting_status"], snapshot["underwriting_status"])
    flash(
        f"Underwriting review saved for application #{application_id} — financing decision is now “{status_label}”.",
        "success",
    )
    return redirect(url_for("admin_application_detail", application_id=application_id))


@bp.route("/admin/applications/<int:application_id>/loan-account", methods=["POST"])
@require_admin_auth
def admin_application_loan_account(application_id: int):
    if not validate_csrf(request.form.get("csrf_token", "")):
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("admin_application_detail", application_id=application_id))

    application = fetch_application(application_id)
    if application is None:
        return Response("Application not found.", status=404)

    actor = getattr(g, "admin_actor", get_request_actor())
    snapshot, validation_error = validate_loan_account_form(request.form, application)
    if validation_error:
        category = "info" if validation_error.startswith("No loan account changes were") else "error"
        flash(validation_error, category)
        return redirect(url_for("admin_application_detail", application_id=application_id))

    context_notes = (request.form.get("loan_account_context") or "").strip()[:1000]

    try:
        persist_loan_account_update(
            application_id,
            application,
            snapshot,
            actor,
            context_notes=context_notes,
        )
    except Exception as exc:
        log_workflow_failure(
            "Loan account update could not be saved",
            application_id=application_id,
            actor=actor,
            error=str(exc),
        )
        flash_operational_error()
        return redirect(url_for("admin_application_detail", application_id=application_id))

    status_label = LOAN_LIFECYCLE_STATUS_LABELS.get(
        snapshot["loan_lifecycle_status"],
        snapshot["loan_lifecycle_status"],
    )
    flash(
        f"Loan account saved for application #{application_id} — lifecycle is now “{status_label}”.",
        "success",
    )
    return redirect(url_for("admin_application_detail", application_id=application_id))


@bp.route("/admin/applications/<int:application_id>/repayments", methods=["POST"])
@require_admin_auth
def admin_application_repayment(application_id: int):
    if not validate_csrf(request.form.get("csrf_token", "")):
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("admin_application_detail", application_id=application_id))

    application = fetch_application(application_id)
    if application is None:
        return Response("Application not found.", status=404)

    actor = getattr(g, "admin_actor", get_request_actor())
    repayment, validation_error = validate_repayment_form(request.form, application)
    if validation_error:
        flash(validation_error, "error")
        return redirect(url_for("admin_application_detail", application_id=application_id))

    try:
        result = persist_repayment(application_id, application, repayment, actor)
    except Exception as exc:
        log_workflow_failure(
            "Repayment could not be recorded",
            application_id=application_id,
            actor=actor,
            error=str(exc),
        )
        flash_operational_error()
        return redirect(url_for("admin_application_detail", application_id=application_id))

    flash_message = (
        f"Repayment of {repayment['payment_amount']} recorded for application #{application_id}. "
        f"Outstanding balance is now {result['balance_after']}."
    )
    if result["paid_in_full"]:
        flash_message += " Loan marked completed."
    flash(flash_message, "success")
    return redirect(url_for("admin_application_detail", application_id=application_id))


@bp.route("/admin/export/repayments")
@require_admin_auth
def admin_export_repayments():
    from constants.reporting import REPAYMENT_EXPORT_COLUMNS

    filters = parse_admin_list_filters(request.args)
    where_sql, where_params = build_applications_where(filters)
    if where_sql:
        application_clause = where_sql.replace(" WHERE ", "", 1)
        repayment_where = f" WHERE a.id IN (SELECT id FROM applications WHERE {application_clause})"
        repayment_params = list(where_params)
    else:
        repayment_where = ""
        repayment_params = []

    conn = get_db_connection()
    cursor = conn.cursor()
    rows = fetch_repayments_for_export(cursor, repayment_where, repayment_params, REPORT_EXPORT_MAX_ROWS)
    conn.close()

    filename = "repayments_export.csv"
    log_admin_export("repayments", filename=filename, row_count=len(rows))
    return make_csv_response(filename, REPAYMENT_EXPORT_COLUMNS, rows)


@bp.route("/admin/applications/<int:application_id>/workflow", methods=["POST"])
@require_admin_auth
def admin_application_workflow(application_id: int):
    if not validate_csrf(request.form.get("csrf_token", "")):
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("admin_application_detail", application_id=application_id))

    application = fetch_application(application_id)
    if application is None:
        return Response("Application not found.", status=404)

    actor = getattr(g, "admin_actor", get_request_actor())
    action = (request.form.get("workflow_action") or "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    officers = fetch_registered_officers(cursor)
    conn.close()

    if action:
        workflow, validation_error = apply_workflow_quick_action(request.form, application)
    else:
        workflow, validation_error = validate_workflow_form(request.form, application)

    if validation_error:
        category = "info" if validation_error.startswith("No workflow changes") else "error"
        flash(validation_error, category)
        return redirect(url_for("admin_application_detail", application_id=application_id))

    if workflow is None:
        flash("Could not save workflow changes. Check the form and try again.", "error")
        return redirect(url_for("admin_application_detail", application_id=application_id))

    workflow["assigned_officer"] = resolve_officer_name(workflow["assigned_officer"], officers)

    before_snapshot = workflow_snapshot_from_row(application)
    after_snapshot = workflow_snapshot_from_workflow(workflow)
    audit_required = requires_audit_context(before_snapshot, after_snapshot, action or None)
    context_notes, audit_error = validate_audit_context(
        request.form.get("audit_context", ""),
        audit_required,
    )
    if audit_error:
        flash(audit_error, "error")
        return redirect(url_for("admin_application_detail", application_id=application_id))

    transition_warning = None
    if before_snapshot["status"] != after_snapshot["status"]:
        transition_warning = is_risky_status_transition_warning(
            before_snapshot["status"],
            after_snapshot["status"],
        )

    try:
        persist_workflow_update(
            application_id,
            application,
            workflow,
            actor,
            quick_action=action or None,
            context_notes=context_notes,
            transition_warning=transition_warning,
        )
    except Exception as exc:
        log_workflow_failure(
            "Workflow update could not be persisted",
            application_id=application_id,
            actor=actor,
            quick_action=action or None,
            error=str(exc),
        )
        flash_operational_error()
        return redirect(url_for("admin_application_detail", application_id=application_id))

    flash_message = (
        f"Workflow saved for application #{application_id} — status is now “{workflow['status']}”. "
        f"Recorded under operator “{actor}”."
    )
    if transition_warning:
        flash_message += f" Note: {transition_warning}"
    flash(flash_message, "success")
    if not workflow["assigned_officer"] and workflow["status"] in KPI_ACTIVE_PIPELINE_STATUSES:
        flash(
            "This pipeline case has no assigned officer. Assign one for operational accountability.",
            "info",
        )
    return redirect(url_for("admin_application_detail", application_id=application_id))


from routes.admin_operations import register_phase_routes

register_phase_routes(bp)