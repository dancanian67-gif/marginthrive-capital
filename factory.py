import os

from dotenv import load_dotenv
from flask import Flask

from repositories.database import init_db
from routes import register_routes
from template_helpers import register_template_globals
from utils.env import get_bool_env, is_development

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-secret-key-change-me")

    register_template_globals(app)
    register_routes(app)

    return app


def run_dev_server() -> None:
    app = create_app()
    if not is_development() and app.config["SECRET_KEY"] == "dev-only-secret-key-change-me":
        raise RuntimeError("Set a strong SECRET_KEY environment variable for non-development environments.")

    init_db()
    debug_mode = is_development() and get_bool_env("FLASK_DEBUG", default=True)
    app.run(debug=debug_mode)
