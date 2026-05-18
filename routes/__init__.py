"""HTTP route registration for MarginThrive Capital."""

from flask import Flask

from routes import admin, public


def _register_legacy_blueprint_endpoints(app: Flask, blueprint_name: str) -> None:
    """Expose pre-blueprint endpoint names used by templates and url_for callers."""
    prefix = f"{blueprint_name}."
    for rule in list(app.url_map.iter_rules()):
        if not rule.endpoint.startswith(prefix):
            continue
        legacy_endpoint = rule.endpoint[len(prefix) :]
        if legacy_endpoint in app.view_functions:
            continue
        methods = sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
        app.add_url_rule(
            rule.rule,
            endpoint=legacy_endpoint,
            view_func=app.view_functions[rule.endpoint],
            methods=methods,
            defaults=rule.defaults,
        )


def register_routes(app: Flask) -> None:
    app.register_blueprint(public.bp)
    app.register_blueprint(admin.bp)
    _register_legacy_blueprint_endpoints(app, "admin")
