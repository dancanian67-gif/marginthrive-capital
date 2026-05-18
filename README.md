# MarginThrive Capital

Minimal Flask app for financing applications and admin review.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set secure values (`SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`). On first startup, these bootstrap the initial administrator operator account when no operators exist yet.
4. Run:
   - `python app.py`

## Project structure (Phase C1–C2)

```
app.py                 # Entry point
factory.py             # Flask app factory
template_helpers.py    # Jinja template globals
constants/             # Domain, workflow, analytics, audit, reporting, operator constants
config/                # Environment-aware Flask configuration
utils/                 # Logging, auth, CSRF, env validation, backup, error handling
repositories/          # SQLite access (applications, audit, officers, operators, database init)
services/              # Workflow, audit, analytics, reporting, filters, intake, operators
routes/                # HTTP routes (public, auth, admin, operators blueprints)
templates/             # Jinja templates and partials
```

## Environment variables

- `APP_ENV` - `development` or `production`
- `FLASK_ENV` - optional Flask env setting
- `FLASK_DEBUG` - `true`/`false` debug toggle (effective in development)
- `SECRET_KEY` - required, must be strong in production
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` - bootstrap the first administrator when the `operators` table is empty
- `ADMIN_EMAIL` / `ADMIN_DISPLAY_NAME` - optional bootstrap profile fields

## Operator authentication (Phase C2)

- `/admin/login` — session-based operator sign-in (replaces HTTP Basic Auth)
- `/admin/logout` — POST sign-out
- `/admin/operators` — administrator-only operator account management
- Passwords are stored as Werkzeug password hashes; sessions expire after 8 hours of inactivity
- Workflow audit history, exports, and governance views attribute actions to the signed-in operator (`display_name (username)` when set)
- Operational roles: `administrator`, `review_officer`, `analyst`, `operations_manager` (all active operators retain access to existing operational routes; only administrators manage operator accounts)

## Production readiness (Phase D1)

- **WSGI entrypoint:** `wsgi:application` (see [docs/OPERATIONS.md](docs/OPERATIONS.md))
- **Health checks:** `GET /health` (live), `GET /health/ready` (database readiness)
- **Operational logging:** structured `marginthrive.ops` logger (`LOG_LEVEL`, optional `LOG_FILE`)
- **Backups:** `python tools/backup_database.py`
- **Login protection:** in-memory lockout after repeated failed sign-ins

Deploy with Gunicorn behind a TLS reverse proxy. Set `APP_ENV=production`, a strong `SECRET_KEY`, and `TRUST_PROXY=true` when using a proxy.

## Production notes

- Do not run with debug enabled in production.
- Set a strong `SECRET_KEY` and bootstrap or provision operator accounts.
- Keep `.env` out of version control.
- See [docs/OPERATIONS.md](docs/OPERATIONS.md) for backup, recovery, and incident guidance.

## Workflow schema (Phase A1)

Applications support operational fields (`status`, `sub_status`, timestamps, risk, officer assignment, etc.). See [docs/WORKFLOW_SCHEMA.md](docs/WORKFLOW_SCHEMA.md). On startup, `init_db()` migrates existing SQLite databases in place without deleting rows.

## Operational audit (Phase B2)

Workflow changes are recorded in `workflow_history` with operator attribution, optional governance notes, and a timeline on each application detail page. See [docs/WORKFLOW_SCHEMA.md](docs/WORKFLOW_SCHEMA.md#operational-audit-trail-phase-b2).

## Underwriting & financing decisions (Phase D2)

Application review includes a dedicated **Underwriting & financing decision** panel on each application detail page. Operators record structured assessments (affordability, repayment confidence, business stability, documentation quality), financing decision status, rationale, and escalation context. Decisions are stored on the application, versioned in `underwriting_decisions`, and mirrored into the governance audit trail separately from pipeline workflow status.

## Reports & exports (Phase B3)

Operational reports and CSV exports are available at `/admin/reports`, with filtered application exports from `/admin` and audit exports from application detail. See [docs/WORKFLOW_SCHEMA.md](docs/WORKFLOW_SCHEMA.md#operational-reports--exports-phase-b3).
