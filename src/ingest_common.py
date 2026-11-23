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
            try:
                rows.append((
                    r["transaction_id"],
                    int(r["account_id"]),
                    date.fromisoformat(r["transaction_date"]),
                    r["transaction_type"],
                    Decimal(r["amount"]),
                    int(r["branch_id"]),
                ))
            except Exception as exc:
                raise ValueError(f"line {line_no}: bad value ({exc})")
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


def run_ingestion(source, target, delimiter):
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

        rows = read_delimited(source, delimiter)
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
