"""Phase 9A Task B.2 — CSV export with formula-injection protection (Phase 2's own existing rule, reused here)."""
import csv
import io

_FORMULA_PREFIXES = ('=', '+', '-', '@')


def _sanitize_cell(value):
    text = '' if value is None else str(value)
    if text and text[0] in _FORMULA_PREFIXES:
        return "'" + text  # a leading apostrophe forces spreadsheet apps to treat it as text, not a formula
    return text


def export_csv(rows: list, column_order: list) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(column_order)
    for row in rows:
        writer.writerow([_sanitize_cell(row.get(col)) for col in column_order])
    return buffer.getvalue()
