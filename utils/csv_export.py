import csv
import io
from collections.abc import Iterable, Iterator

from flask import Response, stream_with_context


def _row_values(columns: tuple[tuple[str, str], ...], row: dict) -> list:
    return [row.get(key, "") for _header, key in columns]


def make_csv_response(filename: str, columns: tuple[tuple[str, str], ...], rows: list[dict]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([header for header, _key in columns])
    for row in rows:
        writer.writerow(_row_values(columns, row))
    payload = buffer.getvalue()
    return Response(
        payload,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def make_streaming_csv_response(
    filename: str,
    columns: tuple[tuple[str, str], ...],
    row_iterator: Iterable[dict],
) -> Response:
    """Stream CSV rows to avoid loading entire exports into memory."""

    def generate() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([header for header, _key in columns])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        for row in row_iterator:
            writer.writerow(_row_values(columns, row))
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return Response(
        stream_with_context(generate()),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def make_sectioned_csv_response(filename: str, sections: list[tuple[str, tuple[tuple[str, str], ...], list[dict]]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for index, (title, columns, rows) in enumerate(sections):
        if index:
            writer.writerow([])
        writer.writerow([f"# {title}"])
        writer.writerow([header for header, _key in columns])
        for row in rows:
            writer.writerow(_row_values(columns, row))
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def make_streaming_sectioned_csv_response(
    filename: str,
    sections: list[tuple[str, tuple[tuple[str, str], ...], Iterable[dict]]],
) -> Response:
    """Stream multi-section CSV when any section uses an iterator."""

    def generate() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for index, (title, columns, rows) in enumerate(sections):
            if index:
                writer.writerow([])
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate(0)
            writer.writerow([f"# {title}"])
            writer.writerow([header for header, _key in columns])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            for row in rows:
                writer.writerow(_row_values(columns, row))
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate(0)

    return Response(
        stream_with_context(generate()),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def distribution_export_rows(items: list[dict], label_key: str = "label") -> list[dict]:
    return [
        {
            "label": item[label_key],
            "count": item["count"],
            "share_pct": item.get("share", ""),
        }
        for item in items
    ]
