import os

from constants.operators import OPERATOR_SESSION_LIFETIME
from utils.env import get_bool_env, is_development, is_production


def configure_app(app) -> None:
    """Apply environment-aware Flask configuration."""
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-secret-key-change-me")
    app.config["PERMANENT_SESSION_LIFETIME"] = OPERATOR_SESSION_LIFETIME
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    app.config["SESSION_REFRESH_EACH_REQUEST"] = True
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024)))

    if is_production():
        app.config["DEBUG"] = False
        app.config["TESTING"] = False
        # Never honor FLASK_DEBUG in production (e.g. Render dashboard misconfiguration).
        app.config["ENV"] = "production"
        app.config["SESSION_COOKIE_SECURE"] = get_bool_env("SESSION_COOKIE_SECURE", default=True)
        app.config["PREFERRED_URL_SCHEME"] = "https" if get_bool_env("FORCE_HTTPS", default=True) else "http"
    else:
        app.config["DEBUG"] = get_bool_env("FLASK_DEBUG", default=True)
        app.config["SESSION_COOKIE_SECURE"] = get_bool_env("SESSION_COOKIE_SECURE", default=False)
        app.config["PREFERRED_URL_SCHEME"] = "http"

    if get_bool_env("TRUST_PROXY", default=is_production()):
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
