"""Cloudinary-backed application document uploads."""

from __future__ import annotations

import os
from typing import BinaryIO

import cloudinary
import cloudinary.uploader
from werkzeug.utils import secure_filename

from constants.documents import (
    ALLOWED_DOCUMENT_TYPES,
    DOCUMENT_TYPE_ID,
    DOCUMENT_TYPE_STATEMENTS,
    ID_CONTENT_TYPES,
    ID_EXTENSIONS,
    MAX_DOCUMENT_UPLOAD_BYTES,
    MAX_FILES_PER_REQUEST,
    STATEMENT_CONTENT_TYPES,
    STATEMENT_EXTENSIONS,
)


def cloudinary_configured() -> bool:
    return bool(
        (os.getenv("CLOUDINARY_CLOUD_NAME") or "").strip()
        and (os.getenv("CLOUDINARY_API_KEY") or "").strip()
        and (os.getenv("CLOUDINARY_API_SECRET") or "").strip()
    )


def _configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name=(os.getenv("CLOUDINARY_CLOUD_NAME") or "").strip(),
        api_key=(os.getenv("CLOUDINARY_API_KEY") or "").strip(),
        api_secret=(os.getenv("CLOUDINARY_API_SECRET") or "").strip(),
        secure=True,
    )


def _file_extension(filename: str) -> str:
    base = secure_filename(filename or "")
    dot = base.rfind(".")
    if dot < 0:
        return ""
    return base[dot:].lower()


def validate_upload_file(file_storage, document_type: str) -> str | None:
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        return "Invalid document type."

    if not file_storage or not file_storage.filename:
        return "No file selected."

    filename = secure_filename(file_storage.filename)
    if not filename:
        return "Invalid file name."

    extension = _file_extension(filename)
    content_type = (file_storage.mimetype or "").split(";")[0].strip().lower()

    if document_type == DOCUMENT_TYPE_ID:
        if extension not in ID_EXTENSIONS:
            return "Identity documents must be JPG or PNG images."
        if content_type and content_type not in ID_CONTENT_TYPES:
            return "Identity documents must be JPG or PNG images."
    else:
        if extension not in STATEMENT_EXTENSIONS:
            return "Financial statements must be PDF files."
        if content_type and content_type not in STATEMENT_CONTENT_TYPES:
            return "Financial statements must be PDF files."

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0:
        return "Uploaded file is empty."
    if size > MAX_DOCUMENT_UPLOAD_BYTES:
        return "File exceeds the 10 MB upload limit."

    return None


def _cloudinary_folder(application_id: int, document_type: str) -> tuple[str, str]:
    if document_type == DOCUMENT_TYPE_ID:
        suffix = "id_documents"
        resource_type = "image"
    else:
        suffix = "statements"
        resource_type = "raw"
    return f"marginthrive/applications/{application_id}/{suffix}", resource_type


def upload_to_cloudinary(
    file_obj: BinaryIO,
    *,
    application_id: int,
    document_type: str,
    filename: str,
) -> dict:
    if not cloudinary_configured():
        raise RuntimeError("Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.")

    _configure_cloudinary()
    folder, resource_type = _cloudinary_folder(application_id, document_type)
    safe_name = secure_filename(filename) or "document"

    return cloudinary.uploader.upload(
        file_obj,
        folder=folder,
        resource_type=resource_type,
        public_id=os.path.splitext(safe_name)[0],
        use_filename=True,
        unique_filename=True,
        overwrite=False,
    )


def process_document_uploads(
    files,
    *,
    application_id: int,
    document_type: str,
    uploaded_by: str,
) -> tuple[list[dict], list[str]]:
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        return [], ["Invalid document type."]

    selected = [item for item in files if item and item.filename]
    if not selected:
        return [], ["Select at least one file to upload."]
    if len(selected) > MAX_FILES_PER_REQUEST:
        return [], [f"You can upload up to {MAX_FILES_PER_REQUEST} files at a time."]

    uploaded: list[dict] = []
    errors: list[str] = []

    for file_storage in selected:
        validation_error = validate_upload_file(file_storage, document_type)
        if validation_error:
            errors.append(f"{file_storage.filename}: {validation_error}")
            continue

        try:
            result = upload_to_cloudinary(
                file_storage.stream,
                application_id=application_id,
                document_type=document_type,
                filename=file_storage.filename,
            )
        except Exception as exc:
            errors.append(f"{file_storage.filename}: upload failed ({exc})")
            continue

        uploaded.append(
            {
                "file_name": secure_filename(file_storage.filename),
                "cloudinary_url": result.get("secure_url") or result.get("url") or "",
                "cloudinary_public_id": result.get("public_id") or "",
            }
        )

    if not uploaded and not errors:
        errors.append("No files were uploaded.")

    return uploaded, errors
