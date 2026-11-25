import csv
import sys
from pathlib import Path

from db import connect, get_environment

OUT = Path("reports") / "branch_daily_summary.csv"
HEADER = ["transaction_date", "branch_id", "transaction_count",
          "deposits", "withdrawals", "transfers", "upi",
          "money_in", "money_out", "net_flow"]

# Assumption (to confirm with the business): DEPOSIT is money in;
# WITHDRAWAL, TRANSFER and UPI are money out.
# The four type columns hold the AMOUNT per transaction type.
SQL = """
SELECT transaction_date, branch_id,
       COUNT(*) AS transaction_count,
       SUM(CASE WHEN transaction_type = 'DEPOSIT'    THEN amount ELSE 0 END) AS deposits,
       SUM(CASE WHEN transaction_type = 'WITHDRAWAL' THEN amount ELSE 0 END) AS withdrawals,
       SUM(CASE WHEN transaction_type = 'TRANSFER'   THEN amount ELSE 0 END) AS transfers,
       SUM(CASE WHEN transaction_type = 'UPI'        THEN amount ELSE 0 END) AS upi
FROM stg_csv
GROUP BY transaction_date, branch_id
ORDER BY transaction_date, branch_id
"""


def main():
    env = get_environment()
    conn = connect()
    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE()")
        db_name = cur.fetchone()[0]
        cur.execute(SQL)
        data = cur.fetchall()
        cur.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM stg_csv")
        total_count, total_amount = cur.fetchone()
    conn.close()

    print(f"Branch summary in {env} database {db_name}")
    if not data:
        print("FAIL: stg_csv is empty, report not written")
        sys.exit(1)

    report = []
    for day, branch, n, dep, wd, tr, upi in data:
        money_in = dep
        money_out = wd + tr + upi
        report.append((day, branch, n, dep, wd, tr, upi,
                       money_in, money_out, money_in - money_out))

    checks = [
        ("transaction count", sum(r[2] for r in report), total_count),
        ("amount by type", sum(r[3] + r[4] + r[5] + r[6] for r in report), total_amount),
        ("money in + money out", sum(r[7] + r[8] for r in report), total_amount),
    ]
    failed = False
    for name, got, expected in checks:
        ok = got == expected
        failed = failed or not ok
        print(f"{'PASS' if ok else 'FAIL'}: tie-out {name}: report {got}, stg_csv {expected}")
    if failed:
        print("Report not written")
        sys.exit(1)

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for r in report:
            writer.writerow([r[0].isoformat(), r[1], r[2]] + [f"{x:.2f}" for x in r[3:]])
    print(f"Wrote {OUT} with {len(report)} rows")


if __name__ == "__main__":
    main()
