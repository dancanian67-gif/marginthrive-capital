

# ALTER TABLE only allows constant defaults; timestamps are backfilled after add.
APPLICATIONS_SCHEMA_COLUMNS = (
    ("status", "TEXT NOT NULL DEFAULT 'New applicant'"),
    ("sub_status", "TEXT"),
    ("created_at", "TEXT"),
    ("updated_at", "TEXT"),
    ("risk_level", "TEXT NOT NULL DEFAULT 'Unassigned'"),
    ("approval_notes", "TEXT NOT NULL DEFAULT ''"),
    ("assigned_officer", "TEXT NOT NULL DEFAULT ''"),
    ("phone_number", "TEXT NOT NULL DEFAULT ''"),
    ("business_type", "TEXT NOT NULL DEFAULT ''"),
    ("date_of_birth", "TEXT"),
    ("gender", "TEXT NOT NULL DEFAULT ''"),
    ("flagged_fraud", "INTEGER NOT NULL DEFAULT 0"),
    ("loan_amount", "REAL"),
)
