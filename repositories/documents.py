"""Application document metadata persistence."""

from constants.documents import DOCUMENT_TYPE_ID, DOCUMENT_TYPE_STATEMENTS


def init_application_documents_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            cloudinary_url TEXT NOT NULL,
            cloudinary_public_id TEXT NOT NULL,
            uploaded_by TEXT NOT NULL,
            uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_application_documents_application
        ON application_documents (application_id, document_type, uploaded_at DESC)
        """
    )


def insert_application_document(
    cursor,
    *,
    application_id: int,
    document_type: str,
    file_name: str,
    cloudinary_url: str,
    cloudinary_public_id: str,
    uploaded_by: str,
) -> int:
    cursor.execute(
        """
        INSERT INTO application_documents (
            application_id,
            document_type,
            file_name,
            cloudinary_url,
            cloudinary_public_id,
            uploaded_by
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            application_id,
            document_type,
            file_name,
            cloudinary_url,
            cloudinary_public_id,
            uploaded_by,
        ),
    )
    return cursor.lastrowid


def fetch_application_documents(cursor, application_id: int) -> list:
    cursor.execute(
        """
        SELECT
            id,
            application_id,
            document_type,
            file_name,
            cloudinary_url,
            cloudinary_public_id,
            uploaded_by,
            uploaded_at
        FROM application_documents
        WHERE application_id = ?
        ORDER BY uploaded_at DESC, id DESC
        """,
        (application_id,),
    )
    return cursor.fetchall()


def group_documents_by_type(rows) -> dict[str, list]:
    grouped = {DOCUMENT_TYPE_ID: [], DOCUMENT_TYPE_STATEMENTS: []}
    for row in rows:
        doc_type = row["document_type"]
        if doc_type in grouped:
            grouped[doc_type].append(row)
    return grouped
