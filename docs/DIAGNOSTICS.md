# Operational diagnostics & smoke tests (Phase E4)

## Commands

| Command | Purpose |
|---------|---------|
| `python tools/operational_diagnostics.py` | Full startup + integrity + deployment summary |
| `python tools/operational_diagnostics.py --json` | Same report as JSON |
| `python tools/integrity_check.py` | Database and governance integrity only |
| `python tools/smoke_test.py` | Isolated regression smoke tests (temp SQLite DB) |
| `python tools/deployment_checklist.py` | Pre-deploy checklist |
| `python tools/backup_database.py` | On-demand backup |

## Startup flow

1. `load_dotenv()` and ops logging configuration
2. `ensure_production_ready()` when `APP_ENV=production` (fail-fast on critical env issues)
3. `create_app()` → `init_db()` → `run_startup_integrity_checks()`
4. Integrity checks from `utils/integrity_checks.py` run during startup (warnings logged; non-fatal)

Development entry: `python app.py`  
Production entry: `gunicorn wsgi:application`

## Smoke-test strategy

- **stdlib `unittest` only** — no pytest dependency
- **Isolated `DATABASE_PATH`** — temp file per run; production `database.db` untouched
- **Bootstrap operator** — `ADMIN_USERNAME` / `ADMIN_PASSWORD` env for smoke admin
- **Coverage** — boot, auth, RBAC denial, workflow audit, underwriting history, loan/repayment, analytics pages, CSV export

## RBAC model (summary)

| Role | Mutations | Exports |
|------|-----------|---------|
| administrator | All | All |
| operations_manager | Workflow, underwriting, loan, repayments | Yes |
| review_officer | Workflow, underwriting | No |
| analyst | Read-only mutations | Yes |

Permissions: `constants/permissions.py` · Enforcement: `utils/permissions.py`

## Governance protections

- Append-only `workflow_history` (no mutating triggers expected)
- Versioned `underwriting_decisions` and `loan_account_history`
- Actor attribution checks on audit tables
- Governance tags in `context_notes` (e.g. `[governance:fraud_override]`)
- Denied actions logged with optional repeated-attempt escalation

## Backup / restore

See [OPERATIONS.md](OPERATIONS.md#database-backup--recovery).
