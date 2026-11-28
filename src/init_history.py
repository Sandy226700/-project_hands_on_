import sys

from db import connect, get_environment

CREATE_HIST = """
CREATE TABLE IF NOT EXISTS transactions_hist (
    transaction_id   VARCHAR(20)   NOT NULL,
    account_id       INT           NOT NULL,
    transaction_date DATE          NOT NULL,
    transaction_type VARCHAR(20)   NOT NULL,
    amount           DECIMAL(12,2) NOT NULL,
    branch_id        INT           NOT NULL,
    source_file      VARCHAR(255)  NOT NULL,
    first_loaded_ts  DATETIME      NOT NULL,
    last_updated_ts  DATETIME      NOT NULL,
    PRIMARY KEY (transaction_id)
)
"""

SEED_SQL = """
INSERT INTO transactions_hist
    (transaction_id, account_id, transaction_date, transaction_type, amount,
     branch_id, source_file, first_loaded_ts, last_updated_ts)
SELECT transaction_id, account_id, transaction_date, transaction_type, amount,
       branch_id, 'initial_load', NOW(), NOW()
FROM stg_csv
"""


def main():
    env = get_environment()
    conn = connect()
    try:
        # CREATE TABLE commits by itself in MySQL, so it comes before the load.
        with conn.cursor() as cur:
            cur.execute(CREATE_HIST)
            cur.execute("SELECT DATABASE()")
            db_name = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM transactions_hist")
            existing = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM stg_csv")
            source = cur.fetchone()[0]
        conn.commit()
        print(f"History seed in {env} database {db_name}")

        if existing > 0:
            print(f"REFUSED: transactions_hist already holds {existing} rows; "
                  "the seed runs only once")
            sys.exit(1)
        if source == 0:
            print("FAIL: stg_csv has no rows, nothing to seed")
            sys.exit(1)

        with conn.cursor() as cur:
            cur.execute(SEED_SQL)
            cur.execute("SELECT COUNT(*) FROM transactions_hist")
            loaded = cur.fetchone()[0]
        if loaded != source:
            raise ValueError(f"count mismatch: stg_csv has {source}, loaded {loaded}")
        conn.commit()
        print(f"SUCCESS: seeded {loaded} of {source} rows from stg_csv")
    except Exception as exc:
        conn.rollback()
        print(f"FAILED: {exc}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
