from flask import url_for

def overview_drilldown_links() -> dict[str, str]:
    return {
        "total_applications": url_for("admin"),
        "active_pipeline": url_for("admin", preset="pipeline"),
        "approved": url_for("admin", preset="approved"),
        "rejected": url_for("admin", preset="rejected"),
        "high_risk": url_for("admin", preset="high_risk"),
        "fraud_flagged": url_for("admin", flagged_fraud="1"),
        "pending_ops_review": url_for("admin", preset="ops_review"),
        "awaiting_client_action": url_for("admin", preset="awaiting_client"),
        "active_loans": url_for("admin", preset="active_loans"),
        "overdue_loans": url_for("admin", preset="overdue_loans"),
    }
