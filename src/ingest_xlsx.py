from datetime import date, datetime

from openpyxl import load_workbook

from ingest_common import COLUMNS, run_ingestion, validate_row


def cell_to_text(value):
    """Convert a typed Excel cell into plain text the shared validation understands."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_xlsx(path):
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"cannot open Excel file: {exc}")
    try:
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        header_row = next(rows_iter, None)
        if header_row is None:
            raise ValueError("Excel sheet is empty")
        header = [cell_to_text(h) for h in header_row]
        missing = [c for c in COLUMNS if c not in header]
        if missing:
            raise ValueError(f"missing columns: {', '.join(missing)}")
        rows = []
        for row_no, values in enumerate(rows_iter, start=2):
            record = {h: cell_to_text(v) for h, v in zip(header, values) if h}
            if all(v == "" for v in record.values()):
                continue
            rows.append(validate_row(record, f"row {row_no}"))
        return rows
    finally:
        wb.close()


if __name__ == "__main__":
    run_ingestion("data/bank_transactions.xlsx", "stg_xlsx", read_xlsx)
