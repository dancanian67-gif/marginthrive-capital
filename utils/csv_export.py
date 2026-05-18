import csv
import io

from flask import Response

def make_csv_response(filename: str, columns: tuple[tuple[str, str], ...], rows: list[dict]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([header for header, _key in columns])
    for row in rows:
        writer.writerow([row.get(key, "") for _header, key in columns])
    payload = buffer.getvalue()
    return Response(
        payload,
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
            writer.writerow([row.get(key, "") for _header, key in columns])
    return Response(
        buffer.getvalue(),
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
