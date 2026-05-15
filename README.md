# MarginThrive Capital

Minimal Flask app for financing applications and admin review.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set secure values (especially `ADMIN_USERNAME` and `ADMIN_PASSWORD` — without them, `/admin` shows “Admin credentials are not configured.”).
4. Run:
   - `python app.py`

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
