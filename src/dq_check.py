import sys
from datetime import datetime

from db import connect, get_environment

CREATE_RESULTS = """
CREATE TABLE IF NOT EXISTS dq_results (
    result_id      INT AUTO_INCREMENT PRIMARY KEY,
    run_ts         DATETIME     NOT NULL,
    rule_id        VARCHAR(10)  NOT NULL,
    severity       VARCHAR(10)  NOT NULL,
    description    VARCHAR(200) NOT NULL,
    offending_rows INT,
    status         VARCHAR(10)  NOT NULL
)
"""

# (rule id, severity, description, SQL that counts the offending rows)
# The thresholds are assumptions to confirm with the business.
RULES = [
    ("R0", "ERROR", "stg_csv has no rows",
     "SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END FROM stg_csv"),
    ("R1", "ERROR", "duplicate business key (account, date, type, amount, branch)",
     "SELECT COALESCE(SUM(c), 0) FROM ("
     "SELECT COUNT(*) AS c FROM stg_csv "
     "GROUP BY account_id, transaction_date, transaction_type, amount, branch_id "
     "HAVING COUNT(*) > 1) t"),
    ("R2", "ERROR", "amount outside 100 to 50000",
     "SELECT COUNT(*) FROM stg_csv WHERE amount < 100 OR amount > 50000"),
    ("R3", "ERROR", "transaction_date in the future",
     "SELECT COUNT(*) FROM stg_csv WHERE transaction_date > CURDATE()"),
    ("R4", "ERROR", "branch_id outside 1 to 10",
     "SELECT COUNT(*) FROM stg_csv WHERE branch_id < 1 OR branch_id > 10"),
    ("R5", "ERROR", "transaction_type not DEPOSIT, WITHDRAWAL, TRANSFER or UPI",
     "SELECT COUNT(*) FROM stg_csv "
     "WHERE transaction_type NOT IN ('DEPOSIT', 'WITHDRAWAL', 'TRANSFER', 'UPI')"),
    ("R6", "WARNING", "accounts with more than 15 transactions",
     "SELECT COUNT(*) FROM ("
     "SELECT account_id FROM stg_csv GROUP BY account_id HAVING COUNT(*) > 15) t"),
]


def main():
    env = get_environment()
    conn = connect()
    with conn.cursor() as cur:
        cur.execute(CREATE_RESULTS)
        cur.execute("SELECT DATABASE()")
        db_name = cur.fetchone()[0]
    conn.commit()
    print(f"Data quality in {env} database {db_name}")

    run_ts = datetime.now()
    results = []
    errors_failed = 0
    warnings = 0
    for rule_id, severity, description, sql in RULES:
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                offending = int(cur.fetchone()[0])
            if offending == 0:
                status = "PASS"
            elif severity == "ERROR":
                status = "FAIL"
            else:
                status = "WARN"
            detail = f"offending: {offending}"
        except Exception as exc:
            offending, status, detail = None, "FAIL", f"error: {exc}"
        if status == "FAIL":
            errors_failed += 1
        if status == "WARN":
            warnings += 1
        results.append((run_ts, rule_id, severity, description, offending, status))
        print(f"{status}: {rule_id} {description} ({detail})")

    # Results are stored before the script exits, even when a rule failed.
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO dq_results "
            "(run_ts, rule_id, severity, description, offending_rows, status) "
            "VALUES (%s, %s, %s, %s, %s, %s)", results)
    conn.commit()
    conn.close()

    print(f"SUMMARY: {errors_failed} error rule(s) failed, {warnings} warning(s)")
    print("Results stored in dq_results")
    sys.exit(1 if errors_failed else 0)


if __name__ == "__main__":
    main()
