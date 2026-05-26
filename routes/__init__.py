"""HTTP route registration for MarginThrive Capital."""

from flask import Flask

from routes import admin, auth, health, operators, public


def _register_legacy_blueprint_endpoints(app: Flask, blueprint_name: str) -> None:
    """Expose pre-blueprint endpoint names used by templates and url_for callers."""
    prefix = f"{blueprint_name}."
    for rule in list(app.url_map.iter_rules()):
        if not rule.endpoint.startswith(prefix):
            continue
        legacy_endpoint = rule.endpoint[len(prefix) :]
        if legacy_endpoint in app.view_functions:
            continue
        view_func = app.view_functions.get(rule.endpoint)
        if view_func is None:
            continue
        methods = sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
        if not methods:
            continue
        app.add_url_rule(
            rule.rule,
            endpoint=legacy_endpoint,
            view_func=view_func,
            methods=methods,
            defaults=rule.defaults,
        )


def _ensure_legacy_endpoint(app: Flask, blueprint_endpoint: str, legacy_endpoint: str) -> None:
    """Register a single legacy alias when auto-discovery skipped it."""
    if legacy_endpoint in app.view_functions:
        return
    view_func = app.view_functions.get(blueprint_endpoint)
    if view_func is None:
        return
    for rule in app.url_map.iter_rules():
        if rule.endpoint != blueprint_endpoint:
            continue
        methods = sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
        if not methods:
            continue
        app.add_url_rule(
            rule.rule,
            endpoint=legacy_endpoint,
            view_func=view_func,
            methods=methods,
            defaults=rule.defaults,
        )
        return


def register_routes(app: Flask) -> None:
    app.register_blueprint(health.bp)
    app.register_blueprint(public.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(operators.bp)
    _register_legacy_blueprint_endpoints(app, "admin")
    _register_legacy_blueprint_endpoints(app, "auth")
    _register_legacy_blueprint_endpoints(app, "operators")
    for blueprint_endpoint, legacy_endpoint in (
        ("auth.admin_login", "admin_login"),
        ("auth.admin_logout", "admin_logout"),
        ("admin.admin_notifications", "admin_notifications"),
        ("operators.admin_operators", "admin_operators"),
    ):
        _ensure_legacy_endpoint(app, blueprint_endpoint, legacy_endpoint)
