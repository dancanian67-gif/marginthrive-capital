# MarginThrive Capital — Operations & Recovery (Phase D1)

## Production deployment

### WSGI entrypoint

Use the bundled WSGI module with a production server such as Gunicorn:

```bash
pip install -r requirements.txt
export APP_ENV=production
export SECRET_KEY="<long-random-secret>"
gunicorn --bind 0.0.0.0:8000 --workers 2 --threads 4 wsgi:application
```

Place a reverse proxy (nginx, Caddy, etc.) in front of the app and terminate TLS there. Set `TRUST_PROXY=true` and `FORCE_HTTPS=true` when the proxy forwards `X-Forwarded-Proto`.

### Health checks

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness — process is running |
| `GET /health/ready` | Readiness — database and required tables are available |

Load balancers can use `/health` for liveness and `/health/ready` for readiness.

## Logging

Operational logs use the `marginthrive.ops` logger and emit structured `event=` fields for:

- authentication success, failure, and lockouts
- export/report generation
- workflow persistence failures
- governance/operator management actions
- startup integrity results
- unexpected exceptions

Configure via environment:

- `LOG_LEVEL` — `DEBUG`, `INFO`, `WARNING` (default: `INFO` in production)
- `LOG_FILE` — optional file path for persistent logs

## Database backup & recovery

### Create a backup

```bash
python tools/backup_database.py
```

Backups are written to `backups/` by default (override with `BACKUP_DIR` or `--destination-dir`).

### Restore from backup

1. Stop the application.
2. Copy the desired backup file over the active database path (`DATABASE_PATH`, default `database.db`).
3. Restart the application and verify `GET /health/ready`.

Always take a fresh backup before manual recovery.

## Startup integrity

On boot, the platform validates:

- production `SECRET_KEY` strength
- database directory writability
- required SQLite tables
- performance index presence (warns if missing; `init_db()` creates them)
- SQLite WAL journal mode (warns if not WAL)
- backup directory availability (warns if missing or not writable; auto-creates `backups/` when possible)
- operator account sanity (active administrators, duplicate usernames)
- presence of operator accounts (warns if none)

Critical misconfiguration in production prevents startup via `ensure_production_ready()`.

## Phase E2 operational warnings

The following are logged only (`marginthrive.ops`, `operational.warning`) and do not block requests:

- Export row counts at or above 5,000 rows
- Export generation slower than 5 seconds (measured when streaming completes)
- Analytics ranges `all` or `90d` on heavy queries
- SQLite `SQLITE_BUSY` retries on workflow commits
- Missing or unwritable optional directories

## Login protection

Failed sign-in attempts are tracked in memory per client/IP and identity. After repeated failures, login is temporarily locked (`LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_SECONDS`). Restarting the process clears lockout state — use a reverse proxy rate limit for stronger protection at scale.

## Phase E4 diagnostics & regression

```bash
python tools/operational_diagnostics.py
python tools/integrity_check.py
python tools/smoke_test.py
python tools/deployment_checklist.py
```

Smoke tests use a **temporary SQLite database** and do not modify your development `database.db`.

### Startup flow

1. Environment validation (`utils/env.py`)
2. `init_db()` migrations and indexes
3. `run_startup_integrity_checks()` — tables, WAL, operators, governance orphans, integrity checks
4. Non-critical issues log as `operational.warning`; production misconfiguration fails fast via `ensure_production_ready()`

### RBAC (Phase E3)

Roles: `administrator`, `operations_manager`, `review_officer`, `analyst`.  
Enforcement: `utils/permissions.py` · Matrix: `constants/permissions.py`.

### Governance regression checks

Non-destructive SQL checks in `utils/integrity_checks.py`:

- Orphaned audit / repayment references
- Actor attribution on governance tables
- Underwriting field consistency
- Repayment balance continuity
- Export type / threshold configuration
- Workflow status validity

## Incident checklist

1. Check `/health/ready` and application logs (`LOG_FILE` or process stdout).
2. Confirm `SECRET_KEY`, database path, and operator accounts.
3. Take a backup before schema or data intervention.
4. Restore from backup only during a controlled maintenance window.
