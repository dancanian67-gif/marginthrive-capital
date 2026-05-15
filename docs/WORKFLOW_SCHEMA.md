# Applications workflow schema (Phase A1)

## Lifecycle statuses (`status`)

1. New applicant
2. Collection of documentation
3. Approval
4. Management approval
5. Signing agreement
6. Final review
7. Pending payments
8. Loan issued

Default for new submissions: **New applicant**.

## Sub-statuses (`sub_status`)

Optional; used while a case is in progress:

- Additional documentation
- Client thinking
- Client to submit documentation
- Branch visit arranged
- Waiting for Other
- Margin to act

## New columns (after legacy fields)

| Column | Type | Default | Notes |
|--------|------|---------|--------|
| `status` | TEXT | New applicant | Primary workflow stage |
| `sub_status` | TEXT | NULL | Optional sub-stage |
| `created_at` | TEXT | `datetime('now')` | ISO-style UTC timestamp |
| `updated_at` | TEXT | `datetime('now')` | Set on insert; update on future edits |
| `risk_level` | TEXT | Unassigned | e.g. Low / Medium / High later |
| `approval_notes` | TEXT | '' | Internal notes |
| `assigned_officer` | TEXT | '' | Ops owner |
| `phone_number` | TEXT | '' | Contact |
| `business_type` | TEXT | '' | Classification |
| `date_of_birth` | TEXT | NULL | ISO date string when captured |
| `gender` | TEXT | '' | As provided |
| `flagged_fraud` | INTEGER | 0 | 0 = no, 1 = flagged |
| `loan_amount` | REAL | NULL | Requested/approved amount |

Legacy columns unchanged: `id`, `business_name`, `owner_name`, `email`, `revenue`, `product`.

## Migration behavior

- Existing `database.db` files receive missing columns via `ALTER TABLE ... ADD COLUMN`.
- Timestamp columns are added without `datetime('now')` defaults (SQLite limitation on `ALTER`); rows are then backfilled with `UPDATE ... SET created_at = datetime('now')`.
- `status` is set to **New applicant** where null after migration.
- No data is deleted.

Constants are defined in `app.py` as `APPLICATION_STATUSES` and `APPLICATION_SUB_STATUSES`.

## Admin workflow routes (Phase A2)

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/admin` | Application list with status, risk, fraud, and Review link |
| GET | `/admin/applications/<id>` | Application detail and workflow form |
| POST | `/admin/applications/<id>/workflow` | Save status, sub-status, risk, officer, notes, fraud flag |

Risk levels: `Unassigned`, `Low`, `Medium`, `High`, `Critical`.

## Admin list operations (Phase A3)

`GET /admin` accepts optional query parameters:

| Parameter | Purpose |
|-----------|---------|
| `status` | Exact status filter |
| `sub_status` | Exact sub-status filter |
| `risk_level` | Exact risk filter |
| `flagged_fraud` | `0` or `1` |
| `assigned_officer` | Partial match (LIKE) |
| `q` | Search business name, owner, email, phone |
| `page` | Pagination (15 per page) |

KPI cards show **portfolio-wide** counts (not filtered). The table respects active filters. Pagination links preserve filter/search query params.

Lifecycle status **Rejected** is available for filtering and workflow updates.
