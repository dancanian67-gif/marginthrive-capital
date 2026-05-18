from flask import Blueprint, jsonify

from utils.startup import run_startup_integrity_checks

bp = Blueprint("health", __name__)


@bp.route("/health")
def health_live():
    return jsonify(
        {
            "status": "ok",
            "service": "marginthrive-capital",
            "check": "live",
        }
    )


@bp.route("/health/ready")
def health_ready():
    checks = run_startup_integrity_checks(log=False)
    status_code = 200 if checks["ready"] else 503
    return jsonify(
        {
            "status": "ready" if checks["ready"] else "degraded",
            "service": "marginthrive-capital",
            "check": "ready",
            "database_ok": checks["database_ok"],
            "tables_ok": checks["tables_ok"],
            "operator_count": checks["operator_count"],
            "env_issue_count": checks["env_issue_count"],
        }
    ), status_code
