"""WSGI entrypoint for production deployment (Phase D1)."""

from dotenv import load_dotenv

load_dotenv()

from factory import initialize_application
from utils.env import is_production
from utils.ops_logging import configure_ops_logging, log_startup
from utils.startup import ensure_production_ready, run_startup_integrity_checks

configure_ops_logging()

if is_production():
    ensure_production_ready()

application = initialize_application()
startup_status = run_startup_integrity_checks(log=False)
log_startup("WSGI application loaded", ready=startup_status["ready"])
