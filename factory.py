import os

from dotenv import load_dotenv
from flask import Flask

from config import configure_app
from constants.operators import role_label
from constants.loans import LOAN_LIFECYCLE_STATUS_LABELS, REPAYMENT_FREQUENCY_LABELS, REPAYMENT_RISK_LABELS
from constants.underwriting import UNDERWRITING_STATUS_LABELS
from repositories.database import init_db
from routes import register_routes
from template_helpers import register_template_globals
from utils.auth import operator_from_session
from utils.csrf import ensure_session_csrf_token
from utils.env import get_bool_env, is_development, is_production
from utils.errors import register_error_handlers
from utils.ops_logging import configure_ops_logging, log_startup
from utils.startup import ensure_production_ready, run_startup_integrity_checks

load_dotenv()
configure_ops_logging()


def create_app() -> Flask:
    app = Flask(__name__)
    configure_app(app)
    register_error_handlers(app)
    register_template_globals(app)
    register_routes(app)

    @app.context_processor
    def inject_operator_context():
        operator = operator_from_session()
        if operator:
            operator = {
                **operator,
                "role_label": role_label(operator["role"]),
            }
        return {
            "current_operator": operator,
            "csrf_token": ensure_session_csrf_token(),
            "underwriting_status_labels": UNDERWRITING_STATUS_LABELS,
            "loan_lifecycle_status_labels": LOAN_LIFECYCLE_STATUS_LABELS,
            "repayment_frequency_labels": REPAYMENT_FREQUENCY_LABELS,
            "repayment_risk_labels": REPAYMENT_RISK_LABELS,
        }

    return app


def initialize_application(*, init_database: bool = True) -> Flask:
    """Create the app, validate production config, and run startup integrity checks."""
    if is_production():
        ensure_production_ready()

    app = create_app()

    if init_database:
        init_db()

    startup_status = run_startup_integrity_checks()
    log_startup("Application initialized", ready=startup_status["ready"], env=app.config.get("ENV", os.getenv("APP_ENV")))
    return app


def run_dev_server(app: Flask | None = None) -> None:
    application = app or initialize_application()
    if not is_development() and application.config["SECRET_KEY"] == "dev-only-secret-key-change-me":
        raise RuntimeError("Set a strong SECRET_KEY environment variable for non-development environments.")

    debug_mode = is_development() and get_bool_env("FLASK_DEBUG", default=True)
    application.run(debug=debug_mode)
