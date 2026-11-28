import sys
from datetime import datetime

from db import connect, get_environment

CREATE_ALERTS = """
CREATE TABLE IF NOT EXISTS alerts (
    alert_id   INT AUTO_INCREMENT PRIMARY KEY,
    alert_key  VARCHAR(100) NOT NULL,
    rule_id    VARCHAR(10)  NOT NULL,
    account_id INT          NOT NULL,
    alert_date DATE         NOT NULL,
    detail     VARCHAR(200) NOT NULL,
    status     VARCHAR(20)  NOT NULL DEFAULT 'NEW',
    created_ts DATETIME     NOT NULL,
    UNIQUE KEY uq_alert_key (alert_key)
)
"""

# Thresholds are assumptions to confirm with the business.
A1_SQL = """
SELECT transaction_id, account_id, transaction_date, amount
FROM stg_csv WHERE amount >= 49000 ORDER BY transaction_id
"""
A2_SQL = """
SELECT account_id, transaction_date, COUNT(*)
FROM stg_csv GROUP BY account_id, transaction_date
HAVING COUNT(*) >= 3 ORDER BY account_id, transaction_date
"""

# A duplicate key does nothing. INSERT IGNORE is avoided on purpose: it would also
# hide other insert errors, while this form only skips duplicates.
INSERT_SQL = """
INSERT INTO alerts (alert_key, rule_id, account_id, alert_date, detail, created_ts)
VALUES (%s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE alert_id = alert_id
"""


def count_rule(cur, rule_id):
    cur.execute("SELECT COUNT(*) FROM alerts WHERE rule_id = %s", (rule_id,))
    return cur.fetchone()[0]


def main():
    env = get_environment()
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_ALERTS)
            cur.execute("SELECT DATABASE()")
            db_name = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM stg_csv")
            source_rows = cur.fetchone()[0]
        conn.commit()
        print(f"Alerts in {env} database {db_name}")
        if source_rows == 0:
            print("FAIL: stg_csv has no rows, no alerts generated")
            sys.exit(1)

        now = datetime.now()
        with conn.cursor() as cur:
            cur.execute(A1_SQL)
            a1 = [(f"A1|{tid}", "A1", acct, day,
                   f"transaction {tid} of {amount:.2f}", now)
                  for tid, acct, day, amount in cur.fetchall()]
            cur.execute(A2_SQL)
            a2 = [(f"A2|{acct}|{day.isoformat()}", "A2", acct, day,
                   f"{n} transactions on the same day", now)
                  for acct, day, n in cur.fetchall()]

            total_new = 0
            for rule_id, label, found in (
                    ("A1", "large transaction (>= 49000)", a1),
                    ("A2", "unusual daily activity (>= 3 per account and day)", a2)):
                before = count_rule(cur, rule_id)
                cur.executemany(INSERT_SQL, found)
                new = count_rule(cur, rule_id) - before
                total_new += new
                print(f"{rule_id} {label}: found {len(found)}, new {new}")

            cur.execute("SELECT status, COUNT(*) FROM alerts GROUP BY status ORDER BY status")
            by_status = ", ".join(f"{s}: {n}" for s, n in cur.fetchall())
        conn.commit()
        print(f"SUMMARY: {total_new} new alert(s); alerts table holds ({by_status})")
    except Exception as exc:
        conn.rollback()
        print(f"FAILED: {exc}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
