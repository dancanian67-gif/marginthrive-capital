# MarginThrive Capital

A Flask-based financing operations platform for business loan applications, operator workflows, underwriting, loan servicing, collections, and executive reporting. Built for internal operator teams with session-based authentication, governance audit trails, and SQLite-backed persistence.

## Features

- **Public intake** — Business financing application form with CSRF protection
- **Operator authentication** — Session sign-in, role-based access, login lockout protection
- **Applications dashboard** — Pipeline filters, workflow updates, officer assignment, KPI views
- **Underwriting & loan servicing** — Structured assessments, lifecycle tracking, manual repayments
- **Collections & recovery** — Delinquency queue, promises, prioritization, recovery analytics
- **Notifications** — Operational alert center with acknowledgement workflow
- **Analytics & reports** — Trends, portfolio intelligence, governed CSV exports
- **Production readiness** — Health checks, structured logging, backups, integrity diagnostics

## Requirements

- Python 3.11+ (3.12+ recommended)
- pip

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_ORG/marginthrive-capital.git
cd marginthrive-capital
```

### 2. Create a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example file and edit values for your environment:

```bash
cp .env.example .env
```

Required for production:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Long random secret (32+ characters) |
| `APP_ENV` | `development` or `production` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Bootstrap first administrator when no operators exist |

See [.env.example](.env.example) for optional settings (database path, logging, backups, proxy).

### 5. Run the application

**Development:**

```bash
python app.py
```

Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/) for the public application form.

**Production (WSGI):**

```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:application
```

Use a TLS reverse proxy in production. See [docs/OPERATIONS.md](docs/OPERATIONS.md).

## Admin access

1. Start the app and open **`/admin/login`**.
2. Sign in with your operator credentials.
3. On first run, set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env` before startup to create the initial administrator account.

> **Placeholder:** Document your organization’s operator onboarding process, password policy, and production admin URL here before sharing the repository publicly.

Default bootstrap credentials in `.env.example` are for local development only — never use them in production.

## Screenshots

> **Placeholder:** Add screenshots for the public application page, admin overview, applications dashboard, collections workspace, and analytics.

| View | Path |
|------|------|
| Public application | `/` |
| Admin overview | `/admin/overview` |
| Applications | `/admin` |
| Collections | `/admin/collections` |
| Analytics | `/admin/analytics` |

Suggested location: `docs/screenshots/` (add image files locally; they are optional for the repo).

## Project structure

```
app.py                 # Development entry point
wsgi.py                # Production WSGI entry point
factory.py             # Flask app factory & context processors
config/                # Environment-aware configuration
constants/             # Domain, workflow, permissions, reporting constants
repositories/          # SQLite data access
services/              # Business logic (workflow, audit, analytics, collections, …)
routes/                # HTTP blueprints (public, auth, admin, operators, health)
templates/             # Jinja templates and dashboard partials
static/                # CSS, JavaScript, assets
utils/                 # Auth, CSRF, logging, backups, diagnostics helpers
tools/                 # Backup, integrity, smoke test, deployment utilities
operational_tests/     # Lightweight regression smoke tests
docs/                  # Operations, workflow schema, diagnostics guides
```

## Health checks

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness |
| `GET /health/ready` | Database readiness |

## Operational tools

```bash
python tools/backup_database.py
python tools/operational_diagnostics.py
python tools/integrity_check.py
python tools/smoke_test.py
python tools/deployment_checklist.py
```

See [docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md) and [docs/OPERATIONS.md](docs/OPERATIONS.md).

## Documentation

- [Workflow schema & audit trail](docs/WORKFLOW_SCHEMA.md)
- [Operations & deployment](docs/OPERATIONS.md)
- [Diagnostics & smoke tests](docs/DIAGNOSTICS.md)
- [Dashboard components](docs/DASHBOARD_COMPONENTS.md)

## Security notes

- Never commit `.env`, `database.db`, `backups/`, or `logs/`.
- Use strong `SECRET_KEY` and unique operator passwords in production.
- Deploy behind HTTPS with `APP_ENV=production` and `TRUST_PROXY=true` when using a reverse proxy.

## License

> **Placeholder:** Add your license (e.g. MIT, proprietary) before publishing.
