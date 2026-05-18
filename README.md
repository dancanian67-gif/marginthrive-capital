# MarginThrive Capital

Minimal Flask app for financing applications and admin review.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set secure values (especially `ADMIN_USERNAME` and `ADMIN_PASSWORD` — without them, `/admin` shows “Admin credentials are not configured.”).
4. Run:
   - `python app.py`

## Project structure (Phase C1)

```
app.py                 # Entry point
factory.py             # Flask app factory
template_helpers.py    # Jinja template globals
constants/             # Domain, workflow, analytics, audit, reporting constants
utils/                 # Auth, CSRF, env, CSV export, time-range SQL helpers
repositories/          # SQLite access (applications, audit, officers, database init)
services/              # Workflow, audit, analytics, reporting, filters, intake
routes/                # HTTP routes (public + admin blueprints)
templates/             # Jinja templates and partials
```

## Environment variables

- `APP_ENV` - `development` or `production`
- `FLASK_ENV` - optional Flask env setting
- `FLASK_DEBUG` - `true`/`false` debug toggle (effective in development)
- `SECRET_KEY` - required, must be strong in production
- `ADMIN_USERNAME` - required for `/admin`
- `ADMIN_PASSWORD` - required for `/admin`

## Production notes

- Do not run with debug enabled in production.
- Set a strong `SECRET_KEY` and admin credentials via environment variables.
- Keep `.env` out of version control.

## Workflow schema (Phase A1)

Applications support operational fields (`status`, `sub_status`, timestamps, risk, officer assignment, etc.). See [docs/WORKFLOW_SCHEMA.md](docs/WORKFLOW_SCHEMA.md). On startup, `init_db()` migrates existing SQLite databases in place without deleting rows.

## Operational audit (Phase B2)

Workflow changes are recorded in `workflow_history` with operator attribution, optional governance notes, and a timeline on each application detail page. See [docs/WORKFLOW_SCHEMA.md](docs/WORKFLOW_SCHEMA.md#operational-audit-trail-phase-b2).

## Reports & exports (Phase B3)

Operational reports and CSV exports are available at `/admin/reports`, with filtered application exports from `/admin` and audit exports from application detail. See [docs/WORKFLOW_SCHEMA.md](docs/WORKFLOW_SCHEMA.md#operational-reports--exports-phase-b3).
