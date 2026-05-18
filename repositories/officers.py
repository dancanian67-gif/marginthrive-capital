from constants.workflow import MAX_ASSIGNED_OFFICER_LENGTH, OFFICER_NAME_PATTERN


def init_officers_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS officers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def seed_officers_table(cursor) -> None:
    cursor.execute(
        """
        SELECT DISTINCT assigned_officer AS name
        FROM applications
        WHERE assigned_officer IS NOT NULL AND TRIM(assigned_officer) != ''
        """
    )
    for row in cursor.fetchall():
        cursor.execute(
            "INSERT OR IGNORE INTO officers (name) VALUES (?)",
            (row["name"],),
        )


def ensure_officer_registered(cursor, officer_name: str) -> None:
    if not officer_name:
        return
    cursor.execute("INSERT OR IGNORE INTO officers (name) VALUES (?)", (officer_name,))


def fetch_registered_officers(cursor) -> list[str]:
    cursor.execute(
        """
        SELECT name FROM officers
        WHERE active = 1
        ORDER BY name COLLATE NOCASE ASC
        """
    )
    registered = [row["name"] for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT DISTINCT assigned_officer AS name
        FROM applications
        WHERE assigned_officer IS NOT NULL AND TRIM(assigned_officer) != ''
        ORDER BY assigned_officer COLLATE NOCASE ASC
        """
    )
    seen = {name.casefold() for name in registered}
    merged = list(registered)
    for row in cursor.fetchall():
        name = row["name"]
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            merged.append(name)
    return merged


def fetch_distinct_officers(cursor) -> list[str]:
    return fetch_registered_officers(cursor)


def normalize_officer_name(raw_value: str) -> str:
    collapsed = " ".join((raw_value or "").split())
    if not collapsed:
        return ""
    if not OFFICER_NAME_PATTERN.match(collapsed):
        return ""
    return collapsed[:MAX_ASSIGNED_OFFICER_LENGTH]


def resolve_officer_name(raw_officer: str, known_officers: list[str]) -> str:
    normalized = normalize_officer_name(raw_officer)
    if not normalized:
        return ""
    for known in known_officers:
        if known.casefold() == normalized.casefold():
            return known
    return normalized

