import sys

from db import connect, get_environment

BIG_TABLES = ["stg_csv", "stg_txt", "stg_json", "stg_xlsx"]
ALL_TABLES = BIG_TABLES + ["stg_pdf"]
COLS = "transaction_id, account_id, transaction_date, transaction_type, amount, branch_id"


def scalar(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]


def count(conn, table):
    return scalar(conn, f"SELECT COUNT(*) FROM {table}")


def only_in_first(conn, a, b):
    """Number of rows that exist in table a but not (identically) in table b."""
    return scalar(conn, f"""
        SELECT COUNT(*) FROM (
            SELECT {COLS} FROM {a}
            EXCEPT
            SELECT {COLS} FROM {b}
        ) t""")


def check_same_counts(conn):
    counts = {t: count(conn, t) for t in BIG_TABLES}
    ok = len(set(counts.values())) == 1
    return ok, ", ".join(f"{t}={n}" for t, n in counts.items())


def check_same_content(conn, table):
    missing = only_in_first(conn, "stg_csv", table)
    extra = only_in_first(conn, table, "stg_csv")
    return missing == 0 and extra == 0, f"only in stg_csv: {missing}, only in {table}: {extra}"


def check_pdf_subset(conn):
    extra = only_in_first(conn, "stg_pdf", "stg_csv")
    return extra == 0, f"rows only in stg_pdf: {extra}"


def check_pdf_complete(conn):
    pdf_rows = count(conn, "stg_pdf")
    csv_rows = scalar(
        conn,
        "SELECT COUNT(*) FROM stg_csv "
        "WHERE account_id IN (SELECT DISTINCT account_id FROM stg_pdf)")
    return pdf_rows == csv_rows, (
        f"stg_pdf has {pdf_rows} rows, stg_csv has {csv_rows} for the same account")


def check_audit(conn, table):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, rows_loaded FROM ingestion_audit "
            "WHERE target_table = %s ORDER BY audit_id DESC LIMIT 1", (table,))
        row = cur.fetchone()
    if row is None:
        return False, "no audit row found"
    status, loaded = row
    actual = count(conn, table)
    return status == "SUCCESS" and loaded == actual, (
        f"latest audit: {status}, rows_loaded={loaded}, actual rows={actual}")


def main():
    env = get_environment()
    conn = connect()
    db_name = scalar(conn, "SELECT DATABASE()")
    print(f"Reconciliation in {env} database {db_name}")

    checks = [
        ("row counts equal across csv, txt, json, xlsx", check_same_counts),
        ("stg_txt content equals stg_csv", lambda c: check_same_content(c, "stg_txt")),
        ("stg_json content equals stg_csv", lambda c: check_same_content(c, "stg_json")),
        ("stg_xlsx content equals stg_csv", lambda c: check_same_content(c, "stg_xlsx")),
        ("stg_pdf rows exist in stg_csv", check_pdf_subset),
        ("stg_pdf holds all rows of its account", check_pdf_complete),
    ]
    for table in ALL_TABLES:
        checks.append((f"latest audit for {table} matches table",
                       lambda c, t=table: check_audit(c, t)))

    failed = 0
    for name, check in checks:
        try:
            ok, detail = check(conn)
        except Exception as exc:
            ok, detail = False, f"error: {exc}"
        if not ok:
            failed += 1
        print(f"{'PASS' if ok else 'FAIL'}: {name} ({detail})")
    conn.close()

    total = len(checks)
    print(f"SUMMARY: {total - failed} of {total} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
