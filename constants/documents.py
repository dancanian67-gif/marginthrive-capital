"""Application document upload constants."""

DOCUMENT_TYPE_ID = "id_documents"
DOCUMENT_TYPE_STATEMENTS = "statements"

DOCUMENT_TYPE_LABELS = {
    DOCUMENT_TYPE_ID: "Identity Documents",
    DOCUMENT_TYPE_STATEMENTS: "Financial Statements & M-Pesa Records",
}

ALLOWED_DOCUMENT_TYPES = frozenset({DOCUMENT_TYPE_ID, DOCUMENT_TYPE_STATEMENTS})

ID_CONTENT_TYPES = frozenset({"image/jpeg", "image/png"})
STATEMENT_CONTENT_TYPES = frozenset({"application/pdf"})

ID_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})
STATEMENT_EXTENSIONS = frozenset({".pdf"})

MAX_DOCUMENT_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_FILES_PER_REQUEST = 10

COLLECTION_DOCUMENTATION_STATUS = "Collection of documentation"
