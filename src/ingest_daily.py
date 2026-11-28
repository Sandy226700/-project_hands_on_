import re
import sys
from datetime import datetime
from pathlib import Path

from db import connect, get_environment
from ingest_common import COLUMNS, CREATE_AUDIT, read_delimited, write_audit

TARGET = "transactions_hist"
FILE_DATE = re.compile(r"transactions_(\d{4}-\d{2}-\d{2})\.csv$")
COLS = ", ".join(COLUMNS)
MAX_LINES = 20

INSERT_SQL = f"""
INSERT INTO {TARGET}
    (transaction_id, account_id, transaction_date, transaction_type, amount,
     branch_id, source_file, first_loaded_ts, last_updated_ts)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

# first_loaded_ts is never touched: it records when we first saw the transaction.
UPDATE_SQL = f"""
UPDATE {TARGET}
SET account_id = %s, transaction_date = %s, transaction_type = %s, amount = %s,
    branch_id = %s, source_file = %s, last_updated_ts = %s
WHERE transaction_id = %s
"""


def fetch_existing(cur, ids):
    existing = {}
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        marks = ", ".join(["%s"] * len(chunk))
        cur.execute(f"SELECT {COLS} FROM {TARGET} WHERE transaction_id IN ({marks})", chunk)
        for row in cur.fetchall():
            existing[row[0]] = row
    return existing


def latest_loaded_date(cur):
    """Date of the latest daily file that was loaded successfully, or None."""
    cur.execute(
        "SELECT source_file FROM ingestion_audit "
        "WHERE target_table = %s AND status = 'SUCCESS'", (TARGET,))
    dates = []
    for (name,) in cur.fetchall():
        m = FILE_DATE.search(name)
        if m:
            dates.append(m.group(1))
    return max(dates) if dates else None


def describe_change(old, new):
    return ", ".join(f"{col} {o} -> {n}"
                     for col, o, n in zip(COLUMNS, old, new) if o != n)


def main():
    if len(sys.argv) != 2:
        print("Usage: python src\\ingest_daily.py data\\daily\\transactions_YYYY-MM-DD.csv")
        sys.exit(1)
    source = Path(sys.argv[1])

    env = get_environment()
    conn = connect()
    with conn.cursor() as cur:
        cur.execute(CREATE_AUDIT)
        cur.execute("SELECT DATABASE()")
        db_name = cur.fetchone()[0]
    conn.commit()
    print(f"Daily load in {env} database {db_name}")

    rows_read = 0
    loaded = 0
    try:
        match = FILE_DATE.search(source.name)
        if not match:
            raise ValueError("file name must look like transactions_YYYY-MM-DD.csv")
        file_date = match.group(1)
        if not source.exists():
            raise FileNotFoundError(f"{source} not found")

        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {TARGET}")
            if cur.fetchone()[0] == 0:
                raise ValueError(f"{TARGET} is empty; run src/init_history.py first")
            latest = latest_loaded_date(cur)
        # An older file would overwrite newer corrections with stale values.
        if latest and file_date < latest:
            raise ValueError(
                f"file date {file_date} is older than the latest loaded file "
                f"({latest}); files must be loaded in date order")

        rows = read_delimited(source, ",")
        rows_read = len(rows)
        if rows_read == 0:
            raise ValueError("source file has no data rows")
        seen = set()
        for line_no, row in enumerate(rows, start=2):
            if row[0] in seen:
                raise ValueError(f"line {line_no}: duplicate transaction_id {row[0]} in the same file")
            seen.add(row[0])

        with conn.cursor() as cur:
            existing = fetch_existing(cur, [r[0] for r in rows])
        new, same, changed = [], [], []
        for row in rows:
            old = existing.get(row[0])
            if old is None:
                new.append(row)
            elif old == row:
                same.append(row)
            else:
                changed.append((old, row))
        late = sum(1 for r in new if r[2].isoformat() < file_date)

        now = datetime.now()
        with conn.cursor() as cur:
            if new:
                cur.executemany(INSERT_SQL, [r + (source.name, now, now) for r in new])
            for old, row in changed:
                cur.execute(UPDATE_SQL, (row[1], row[2], row[3], row[4], row[5],
                                         source.name, now, row[0]))
        conn.commit()

        loaded = len(new) + len(changed)
        message = (f"new {len(new)} (late arrivals: {late}), "
                   f"unchanged {len(same)}, updated {len(changed)}")
        write_audit(conn, source.name, TARGET, rows_read, loaded, "SUCCESS", message)
        print(f"SUCCESS: {source.name}: {rows_read} rows read, {message}")
        for old, row in changed[:MAX_LINES]:
            print(f"  updated {row[0]}: {describe_change(old, row)}")
        if len(changed) > MAX_LINES:
            print(f"  ... and {len(changed) - MAX_LINES} more")

    except Exception as exc:
        conn.rollback()
        write_audit(conn, source.name, TARGET, rows_read, 0, "FAILED", str(exc))
        print(f"FAILED: {exc}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
