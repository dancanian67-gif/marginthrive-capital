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
- presence of operator accounts (warns if none)

Critical misconfiguration in production prevents startup via `ensure_production_ready()`.

## Login protection

Failed sign-in attempts are tracked in memory per client/IP and identity. After repeated failures, login is temporarily locked (`LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_SECONDS`). Restarting the process clears lockout state — use a reverse proxy rate limit for stronger protection at scale.

## Incident checklist

1. Check `/health/ready` and application logs (`LOG_FILE` or process stdout).
2. Confirm `SECRET_KEY`, database path, and operator accounts.
3. Take a backup before schema or data intervention.
4. Restore from backup only during a controlled maintenance window.
