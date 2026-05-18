from flask import url_for

from constants.loans import ACTIVE_LOAN_LIFECYCLE_STATUSES, LOAN_LIFECYCLE_STATUSES
from constants.workflow import (
    ADMIN_FILTER_PRESETS,
    ADMIN_LIST_FILTER_KEYS,
    ADMIN_SEARCH_MAX_LENGTH,
    APPLICATION_RISK_LEVELS,
    APPLICATION_STATUSES,
    APPLICATION_SUB_STATUSES,
    KPI_ACTIVE_PIPELINE_STATUSES,
    KPI_APPROVED_STATUSES,
    KPI_CLIENT_ACTION_SUB_STATUSES,
    KPI_HIGH_RISK_LEVELS,
    KPI_OPS_REVIEW_SUB_STATUS,
    KPI_REJECTED_STATUS,
    MAX_ASSIGNED_OFFICER_LENGTH,
)

def parse_admin_list_filters(args) -> dict:
    status = (args.get("status") or "").strip()
    if status and status not in APPLICATION_STATUSES:
        status = ""

    sub_status = (args.get("sub_status") or "").strip()
    if sub_status and sub_status not in APPLICATION_SUB_STATUSES:
        sub_status = ""

    risk_level = (args.get("risk_level") or "").strip()
    if risk_level and risk_level not in APPLICATION_RISK_LEVELS:
        risk_level = ""

    flagged_fraud = (args.get("flagged_fraud") or "").strip()
    if flagged_fraud not in {"", "0", "1"}:
        flagged_fraud = ""

    loan_lifecycle_status = (args.get("loan_lifecycle_status") or "").strip()
    if loan_lifecycle_status and loan_lifecycle_status not in LOAN_LIFECYCLE_STATUSES:
        loan_lifecycle_status = ""

    assigned_officer = (args.get("assigned_officer") or "").strip()
    if len(assigned_officer) > MAX_ASSIGNED_OFFICER_LENGTH:
        assigned_officer = assigned_officer[:MAX_ASSIGNED_OFFICER_LENGTH]

    search_query = (args.get("q") or "").strip()
    if len(search_query) > ADMIN_SEARCH_MAX_LENGTH:
        search_query = search_query[:ADMIN_SEARCH_MAX_LENGTH]

    preset = (args.get("preset") or "").strip()
    if preset not in ADMIN_FILTER_PRESETS:
        preset = ""

    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    return {
        "status": status,
        "sub_status": sub_status,
        "risk_level": risk_level,
        "flagged_fraud": flagged_fraud,
        "loan_lifecycle_status": loan_lifecycle_status,
        "assigned_officer": assigned_officer,
        "q": search_query,
        "preset": preset,
        "page": page,
    }


def build_applications_where(filters: dict) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []

    preset = filters.get("preset") or ""
    if preset == "pipeline":
        placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
        clauses.append(f"status IN ({placeholders})")
        params.extend(KPI_ACTIVE_PIPELINE_STATUSES)
    elif preset == "approved":
        placeholders = ", ".join("?" * len(KPI_APPROVED_STATUSES))
        clauses.append(f"status IN ({placeholders})")
        params.extend(KPI_APPROVED_STATUSES)
    elif preset == "rejected":
        clauses.append("status = ?")
        params.append(KPI_REJECTED_STATUS)
    elif preset == "high_risk":
        placeholders = ", ".join("?" * len(KPI_HIGH_RISK_LEVELS))
        clauses.append(f"risk_level IN ({placeholders})")
        params.extend(KPI_HIGH_RISK_LEVELS)
    elif preset == "awaiting_client":
        placeholders = ", ".join("?" * len(KPI_CLIENT_ACTION_SUB_STATUSES))
        clauses.append(f"sub_status IN ({placeholders})")
        params.extend(KPI_CLIENT_ACTION_SUB_STATUSES)
    elif preset == "ops_review":
        pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
        clauses.append(
            f"(sub_status = ? OR (status IN ({pipeline_placeholders}) AND "
            "(assigned_officer IS NULL OR TRIM(assigned_officer) = '')))"
        )
        params.append(KPI_OPS_REVIEW_SUB_STATUS)
        params.extend(KPI_ACTIVE_PIPELINE_STATUSES)
    elif preset == "active_loans":
        placeholders = ", ".join("?" * len(ACTIVE_LOAN_LIFECYCLE_STATUSES))
        clauses.append(f"loan_lifecycle_status IN ({placeholders})")
        params.extend(ACTIVE_LOAN_LIFECYCLE_STATUSES)
    elif preset == "overdue_loans":
        active_placeholders = ", ".join("?" * len(ACTIVE_LOAN_LIFECYCLE_STATUSES))
        clauses.append(
            f"(loan_lifecycle_status = 'overdue' OR ("
            f"loan_lifecycle_status IN ({active_placeholders}) "
            f"AND due_date IS NOT NULL AND TRIM(due_date) != '' "
            f"AND date(due_date) < date('now') "
            f"AND COALESCE(outstanding_balance, 0) > 0))"
        )
        params.extend(ACTIVE_LOAN_LIFECYCLE_STATUSES)

    if filters["status"]:
        clauses.append("status = ?")
        params.append(filters["status"])

    if filters["sub_status"]:
        clauses.append("sub_status = ?")
        params.append(filters["sub_status"])

    if filters["risk_level"]:
        clauses.append("risk_level = ?")
        params.append(filters["risk_level"])

    if filters["flagged_fraud"] in {"0", "1"}:
        clauses.append("flagged_fraud = ?")
        params.append(int(filters["flagged_fraud"]))

    if filters.get("loan_lifecycle_status"):
        clauses.append("loan_lifecycle_status = ?")
        params.append(filters["loan_lifecycle_status"])

    if filters["assigned_officer"]:
        clauses.append("assigned_officer LIKE ?")
        params.append(f"%{filters['assigned_officer']}%")

    if filters["q"]:
        like_term = f"%{filters['q']}%"
        clauses.append(
            "(business_name LIKE ? OR owner_name LIKE ? OR email LIKE ? OR phone_number LIKE ?)"
        )
        params.extend([like_term, like_term, like_term, like_term])

    if clauses:
        return " WHERE " + " AND ".join(clauses), params
    return "", params


def filters_to_query_params(filters: dict) -> dict:
    return {key: filters[key] for key in ADMIN_LIST_FILTER_KEYS if filters.get(key)}
def filters_have_constraints(filters: dict) -> bool:
    return any(filters.get(key) for key in ADMIN_LIST_FILTER_KEYS)


def active_filter_chips(filters: dict) -> list[dict]:
    chips: list[dict] = []
    preset = filters.get("preset") or ""
    if preset in ADMIN_FILTER_PRESETS:
        chips.append(
            {
                "label": ADMIN_FILTER_PRESETS[preset],
                "clear_url": url_for("admin", **{k: v for k, v in filters_to_query_params(filters).items() if k != "preset"}),
            }
        )
    if filters.get("status"):
        chips.append(
            {
                "label": f"Status: {filters['status']}",
                "clear_url": url_for("admin", **{k: v for k, v in filters_to_query_params(filters).items() if k != "status"}),
            }
        )
    if filters.get("sub_status"):
        chips.append(
            {
                "label": f"Sub-status: {filters['sub_status']}",
                "clear_url": url_for("admin", **{k: v for k, v in filters_to_query_params(filters).items() if k != "sub_status"}),
            }
        )
    if filters.get("risk_level"):
        chips.append(
            {
                "label": f"Risk: {filters['risk_level']}",
                "clear_url": url_for("admin", **{k: v for k, v in filters_to_query_params(filters).items() if k != "risk_level"}),
            }
        )
    if filters.get("flagged_fraud") == "1":
        chips.append(
            {
                "label": "Fraud flagged",
                "clear_url": url_for("admin", **{k: v for k, v in filters_to_query_params(filters).items() if k != "flagged_fraud"}),
            }
        )
    elif filters.get("flagged_fraud") == "0":
        chips.append(
            {
                "label": "Not fraud flagged",
                "clear_url": url_for("admin", **{k: v for k, v in filters_to_query_params(filters).items() if k != "flagged_fraud"}),
            }
        )
    if filters.get("assigned_officer"):
        chips.append(
            {
                "label": f"Officer: {filters['assigned_officer']}",
                "clear_url": url_for(
                    "admin",
                    **{k: v for k, v in filters_to_query_params(filters).items() if k != "assigned_officer"},
                ),
            }
        )
    if filters.get("loan_lifecycle_status"):
        from constants.loans import LOAN_LIFECYCLE_STATUS_LABELS

        lifecycle_label = LOAN_LIFECYCLE_STATUS_LABELS.get(
            filters["loan_lifecycle_status"],
            filters["loan_lifecycle_status"],
        )
        chips.append(
            {
                "label": f"Loan: {lifecycle_label}",
                "clear_url": url_for(
                    "admin",
                    **{
                        k: v
                        for k, v in filters_to_query_params(filters).items()
                        if k != "loan_lifecycle_status"
                    },
                ),
            }
        )
    if filters.get("q"):
        chips.append(
            {
                "label": f"Search: “{filters['q']}”",
                "clear_url": url_for("admin", **{k: v for k, v in filters_to_query_params(filters).items() if k != "q"}),
            }
        )
    return chips


def safe_return_url(candidate: str | None) -> str:
    value = (candidate or "").strip()
    if value.startswith("/admin"):
        return value
    return url_for("admin")
