from constants.workflow import (
    KPI_APPROVED_STATUSES,
    KPI_HIGH_RISK_LEVELS,
    KPI_PENDING_STATUSES,
    KPI_REJECTED_STATUS,
    WORKFLOW_STATUS_GROUPS,
    WORKFLOW_SUB_STATUS_GROUPS,
)
from services.workflow import application_needs_attention


def register_template_globals(app) -> None:
    @app.template_global()
    def dashboard_risk_badge_class(risk_level: str) -> str:
        mapping = {
            "Low": "dashboard-badge-risk-low",
            "Medium": "dashboard-badge-risk-medium",
            "High": "dashboard-badge-risk-high",
            "Critical": "dashboard-badge-risk-critical",
        }
        return mapping.get(risk_level, "dashboard-badge-risk-neutral")

    @app.template_global()
    def dashboard_status_badge_class(status: str) -> str:
        if status == KPI_REJECTED_STATUS:
            return "dashboard-badge-status-rejected"
        if status in KPI_APPROVED_STATUSES:
            return "dashboard-badge-status-approved"
        if status in KPI_PENDING_STATUSES:
            return "dashboard-badge-status-pending"
        return "dashboard-badge-status-neutral"

    @app.template_global()
    def dashboard_table_row_class(application) -> str:
        classes = []
        if application["flagged_fraud"]:
            classes.append("dashboard-table-row-fraud")
        elif application["risk_level"] in KPI_HIGH_RISK_LEVELS:
            classes.append("dashboard-table-row-high-risk")
        elif application_needs_attention(application):
            classes.append("dashboard-table-row-attention")
        return " ".join(classes)

    @app.template_global()
    def dashboard_workflow_status_groups():
        return WORKFLOW_STATUS_GROUPS

    @app.template_global()
    def dashboard_workflow_sub_status_groups():
        return WORKFLOW_SUB_STATUS_GROUPS

    @app.template_global()
    def dashboard_history_batch_class(batch: dict) -> str:
        classes: list[str] = []
        if batch.get("is_critical"):
            classes.append("dashboard-history-batch-critical")
        if batch.get("transition_warning"):
            classes.append("dashboard-history-batch-warning")
        return " ".join(classes)

    @app.template_global()
    def dashboard_underwriting_badge_class(status: str) -> str:
        mapping = {
            "approved": "dashboard-badge-status-approved",
            "conditionally_approved": "dashboard-badge-underwriting-conditional",
            "rejected": "dashboard-badge-status-rejected",
            "escalated_review": "dashboard-badge-underwriting-escalated",
            "pending_clarification": "dashboard-badge-underwriting-clarification",
            "in_review": "dashboard-badge-underwriting-review",
            "pending_review": "dashboard-badge-status-pending",
        }
        return mapping.get(status, "dashboard-badge-status-neutral")

    @app.template_global()
    def dashboard_history_action_label(action_type: str) -> str:
        labels = {
            "application_created": "Application created",
            "workflow_update": "Workflow update",
            "underwriting_update": "Underwriting review",
            "underwriting_status_change": "Financing decision status",
            "underwriting_assessment_change": "Underwriting assessment",
            "underwriting_observation_change": "Underwriting observation",
            "underwriting_decision_change": "Financing decision detail",
            "underwriting_escalation_change": "Underwriting escalation",
            "underwriting_notes_change": "Underwriting notes",
            "underwriting_review_attribution": "Underwriting reviewer",
            "quick_action_advance": "Quick action: advance status",
            "quick_action_margin_to_act": "Quick action: Margin to act",
            "quick_action_clear_sub_status": "Quick action: clear sub-status",
            "quick_action_high_risk": "Quick action: set high risk",
            "quick_action_clear_fraud": "Quick action: clear fraud flag",
            "status_change": "Status change",
            "sub_status_change": "Sub-status change",
            "risk_level_change": "Risk level change",
            "fraud_flag_change": "Fraud flag change",
            "officer_assignment": "Officer assignment",
            "notes_update": "Notes update",
        }
        return labels.get(action_type, action_type.replace("_", " ").title())
