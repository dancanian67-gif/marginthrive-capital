"""Portfolio intelligence orchestration and executive insights (Phase E1)."""

from services.analytics import fill_daily_trend, prepare_trend_chart
from repositories.portfolio import (
    fetch_collections_workload,
    fetch_operational_throughput,
    fetch_portfolio_aging_distribution,
    fetch_portfolio_financial_snapshot,
    fetch_repayment_performance_period,
    fetch_repayment_trend,
    fetch_underwriting_decision_trend,
    fetch_underwriting_outcome_summary,
)


def build_portfolio_intelligence_package(cursor, range_key: str) -> dict:
    """Aggregate live portfolio metrics and period-scoped performance analytics."""
    financial = fetch_portfolio_financial_snapshot(cursor)
    aging = fetch_portfolio_aging_distribution(cursor)
    aging_total = sum(item["count"] for item in aging) or 1
    for item in aging:
        item["share"] = round((item["count"] / aging_total) * 100, 1)

    repayment_trend_raw = fetch_repayment_trend(cursor, range_key)
    repayment_trend = prepare_trend_chart(
        [
            {"label": row["label"], "count": row["count"]}
            for row in fill_daily_trend(
                [{"label": r["label"], "count": r["count"]} for r in repayment_trend_raw],
                range_key,
            )
        ]
    )
    repayment_amount_trend = repayment_trend_raw

    underwriting_outcomes = fetch_underwriting_outcome_summary(cursor, range_key)
    underwriting_trend = fetch_underwriting_decision_trend(cursor, range_key)
    repayment_performance = fetch_repayment_performance_period(cursor, range_key)
    collections_workload = fetch_collections_workload(cursor)
    throughput = fetch_operational_throughput(cursor, range_key)

    return {
        "financial": financial,
        "aging": aging,
        "repayment_trend": repayment_trend,
        "repayment_amount_trend": repayment_amount_trend,
        "underwriting_outcomes": underwriting_outcomes,
        "underwriting_trend": underwriting_trend,
        "repayment_performance": repayment_performance,
        "collections_workload": collections_workload,
        "throughput": throughput,
        "insights": portfolio_insights(financial, underwriting_outcomes, repayment_performance, throughput),
    }


def portfolio_insights(
    financial: dict,
    underwriting_outcomes: dict,
    repayment_performance: dict,
    throughput: dict,
) -> list[str]:
    insights: list[str] = []

    if financial["issued_loan_count"]:
        insights.append(
            f"Live portfolio: {financial['active_loan_count']} active loans, "
            f"{financial['total_outstanding']:,.2f} outstanding, "
            f"{financial['repayment_completion_ratio']}% of issued capital repaid."
        )
    if financial["overdue_exposure"] > 0:
        insights.append(
            f"Overdue exposure: {financial['overdue_exposure']:,.2f} across "
            f"{financial['overdue_loan_count']} loan(s) "
            f"(delinquency ratio {financial['delinquency_ratio']}%)."
        )
    if financial["collections_exposure"] > 0:
        insights.append(
            f"Collections exposure (at-risk + overdue): {financial['collections_exposure']:,.2f}."
        )
    if financial["default_exposure"] > 0:
        insights.append(
            f"Distressed/default exposure: {financial['default_exposure']:,.2f} "
            f"({financial['distressed_loan_count']} account(s))."
        )
    if underwriting_outcomes["total_reviewed"]:
        insights.append(
            f"Financing decisions in period: {underwriting_outcomes['total_reviewed']} reviewed — "
            f"{underwriting_outcomes['approval_rate']}% approved, "
            f"{underwriting_outcomes['rejection_rate']}% rejected."
        )
        if underwriting_outcomes["escalated"]:
            insights.append(
                f"{underwriting_outcomes['escalated']} escalated review(s) in period."
            )
    if repayment_performance["payment_count"]:
        insights.append(
            f"Repayments in period: {repayment_performance['payment_count']} payments "
            f"totalling {repayment_performance['payment_total']:,.2f}."
        )
    if throughput["loans_activated"]:
        insights.append(
            f"Throughput: {throughput['loans_activated']} loan(s) issued, "
            f"{throughput['repayments_recorded']} repayment(s) recorded in period."
        )
    if not insights and financial["issued_loan_count"] == 0:
        insights.append(
            "No issued loan accounts yet — portfolio financial metrics will populate after loan activation."
        )
    return insights[:6]


def portfolio_export_metric_rows(financial: dict, underwriting_outcomes: dict, throughput: dict) -> list[dict]:
    rows = [
        {"metric": "Active portfolio value", "value": financial["active_portfolio_value"]},
        {"metric": "Total outstanding balances", "value": financial["total_outstanding"]},
        {"metric": "Total issued capital", "value": financial["total_issued_capital"]},
        {"metric": "Total repaid capital", "value": financial["total_repaid_capital"]},
        {"metric": "Repayment completion ratio %", "value": financial["repayment_completion_ratio"]},
        {"metric": "Average repayment progress (active) %", "value": financial["avg_repayment_progress_active"]},
        {"metric": "Loan completion rate %", "value": financial["loan_completion_rate"]},
        {"metric": "Overdue portfolio exposure", "value": financial["overdue_exposure"]},
        {"metric": "Default/distressed exposure", "value": financial["default_exposure"]},
        {"metric": "Collections exposure", "value": financial["collections_exposure"]},
        {"metric": "Delinquency ratio %", "value": financial["delinquency_ratio"]},
        {"metric": "Active loans (count)", "value": financial["active_loan_count"]},
        {"metric": "Overdue loans (count)", "value": financial["overdue_loan_count"]},
        {"metric": "Period — applications created", "value": throughput["applications_created"]},
        {"metric": "Period — loans activated", "value": throughput["loans_activated"]},
        {"metric": "Period — repayments recorded", "value": throughput["repayments_recorded"]},
        {"metric": "Period — repayment volume", "value": throughput["repayment_volume"]},
        {"metric": "Period — financing reviews", "value": underwriting_outcomes["total_reviewed"]},
        {"metric": "Period — approval rate %", "value": underwriting_outcomes["approval_rate"]},
        {"metric": "Period — rejection rate %", "value": underwriting_outcomes["rejection_rate"]},
    ]
    return rows
