import csv
from datetime import datetime
from pathlib import Path

from db import connect

SOURCE = Path("data") / "bank_transactions.csv"
TARGET = "stg_csv"

CREATE_STG = """
CREATE TABLE IF NOT EXISTS stg_csv (
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

INSERT_SQL = """
INSERT INTO stg_csv
    (transaction_id, account_id, transaction_date, transaction_type,
     amount, branch_id, load_ts)
VALUES (%s, %s, %s, %s, %s, %s, %s)
"""


def write_audit(conn, rows_read, rows_loaded, status, message):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ingestion_audit "
            "(source_file, target_table, rows_read, rows_loaded, status, message, run_ts) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (SOURCE.name, TARGET, rows_read, rows_loaded, status,
             message[:500], datetime.now()),
        )
    conn.commit()


def main():
    conn = connect()

    # Table creation first: in MySQL, CREATE TABLE commits by itself,
    # so it must not happen inside the load transaction.
    with conn.cursor() as cur:
        cur.execute(CREATE_STG)
        cur.execute(CREATE_AUDIT)
    conn.commit()

    rows_read = 0
    rows_loaded = 0
    try:
        if not SOURCE.exists():
            raise FileNotFoundError(f"{SOURCE} not found")

        with open(SOURCE, newline="") as f:
            rows = list(csv.DictReader(f))
        rows_read = len(rows)
        if rows_read == 0:
            raise ValueError("source file has no data rows")

        load_ts = datetime.now()
        data = [
            (r["transaction_id"], int(r["account_id"]), r["transaction_date"],
             r["transaction_type"], r["amount"], int(r["branch_id"]), load_ts)
            for r in rows
        ]

        # One transaction: delete old rows, insert new rows, check, commit.
        # DELETE (not TRUNCATE) because TRUNCATE commits by itself in MySQL.
        with conn.cursor() as cur:
            cur.execute("DELETE FROM stg_csv")
            cur.executemany(INSERT_SQL, data)
            cur.execute("SELECT COUNT(*) FROM stg_csv")
            rows_loaded = cur.fetchone()[0]

        if rows_loaded != rows_read:
            raise ValueError(f"count mismatch: read {rows_read}, loaded {rows_loaded}")

        conn.commit()
        write_audit(conn, rows_read, rows_loaded, "SUCCESS", "Loaded OK")
        print(f"SUCCESS: loaded {rows_loaded} of {rows_read} rows into {TARGET}")

    except Exception as exc:
        conn.rollback()
        write_audit(conn, rows_read, 0, "FAILED", str(exc))
        print(f"FAILED: {exc}")
        raise SystemExit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
