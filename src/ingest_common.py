import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from db import connect

COLUMNS = ["transaction_id", "account_id", "transaction_date",
           "transaction_type", "amount", "branch_id"]

CREATE_STG = """
CREATE TABLE IF NOT EXISTS {table} (
    transaction_id   VARCHAR(20)   NOT NULL,
    account_id       INT           NOT NULL,
    transaction_date DATE          NOT NULL,
    transaction_type VARCHAR(20)   NOT NULL,
    amount           DECIMAL(12,2) NOT NULL,
    branch_id        INT           NOT NULL,
    load_ts          DATETIME      NOT NULL,
    PRIMARY KEY (transaction_id)
)
"""

CREATE_AUDIT = """
CREATE TABLE IF NOT EXISTS ingestion_audit (
    audit_id     INT AUTO_INCREMENT PRIMARY KEY,
    source_file  VARCHAR(255) NOT NULL,
    target_table VARCHAR(64)  NOT NULL,
    rows_read    INT          NOT NULL,
    rows_loaded  INT          NOT NULL,
    status       VARCHAR(20)  NOT NULL,
    message      VARCHAR(500),
    run_ts       DATETIME     NOT NULL
)
"""

INSERT_STG = """
INSERT INTO {table}
    (transaction_id, account_id, transaction_date, transaction_type,
     amount, branch_id, load_ts)
VALUES (%s, %s, %s, %s, %s, %s, %s)
"""


def convert_amount(text):
    value = Decimal(text)
    if not value.is_finite():
        raise ValueError("amount must be a finite number")
    return value


FIELD_CONVERTERS = [
    ("transaction_id", str),
    ("account_id", int),
    ("transaction_date", date.fromisoformat),
    ("transaction_type", str),
    ("amount", convert_amount),
    ("branch_id", int),
]


def validate_row(record, where):
    """Check one record (a dict of raw values) and return a typed row tuple.

    `where` says where the record came from, e.g. "line 1002" for a text
    file or "record 1002" for JSON, so errors always name the place, the
    column and the invalid value.
    """
    row = []
    for column, convert in FIELD_CONVERTERS:
        raw = record.get(column)
        text = "" if raw is None else str(raw).strip()
        if text == "":
            raise ValueError(f"{where}: column {column} is missing or empty")
        try:
            row.append(convert(text))
        except Exception:
            raise ValueError(f"{where}: column {column} has invalid value '{text}'")
    return tuple(row)


def read_delimited(path, delimiter):
    """Read a delimited text file and return validated, typed rows."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"missing columns: {', '.join(missing)}")
        rows = []
        for line_no, r in enumerate(reader, start=2):
            if None in r:
                raise ValueError(f"line {line_no}: too many fields")
            rows.append(validate_row(r, f"line {line_no}"))
    return rows


def write_audit(conn, source_name, target, rows_read, rows_loaded, status, message):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ingestion_audit "
            "(source_file, target_table, rows_read, rows_loaded, status, message, run_ts) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (source_name, target, rows_read, rows_loaded, status,
             message[:500], datetime.now()),
        )
    conn.commit()


def run_ingestion(source, target, reader):
    """Load `source` into `target`. `reader(path)` returns validated rows."""
    source = Path(source)
    conn = connect()

    # Table creation first: in MySQL, CREATE TABLE commits by itself,
    # so it must not happen inside the load transaction.
    with conn.cursor() as cur:
        cur.execute(CREATE_STG.format(table=target))
        cur.execute(CREATE_AUDIT)
    conn.commit()

    rows_read = 0
    rows_loaded = 0
    try:
        if not source.exists():
            raise FileNotFoundError(f"{source} not found")

        rows = reader(source)
        rows_read = len(rows)
        if rows_read == 0:
            raise ValueError("source file has no data rows")

        load_ts = datetime.now()
        data = [row + (load_ts,) for row in rows]

        # One transaction: delete old rows, insert new rows, check, commit.
        # DELETE (not TRUNCATE) because TRUNCATE commits by itself in MySQL.
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {target}")
            cur.executemany(INSERT_STG.format(table=target), data)
            cur.execute(f"SELECT COUNT(*) FROM {target}")
            rows_loaded = cur.fetchone()[0]

        if rows_loaded != rows_read:
            raise ValueError(f"count mismatch: read {rows_read}, loaded {rows_loaded}")

        conn.commit()
        write_audit(conn, source.name, target, rows_read, rows_loaded, "SUCCESS", "Loaded OK")
        print(f"SUCCESS: loaded {rows_loaded} of {rows_read} rows into {target}")

    except Exception as exc:
        conn.rollback()
        write_audit(conn, source.name, target, rows_read, 0, "FAILED", str(exc))
        print(f"FAILED: {exc}")
        raise SystemExit(1)
    finally:
        conn.close()
