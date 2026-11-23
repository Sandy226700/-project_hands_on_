import os

import pymysql
from dotenv import load_dotenv

load_dotenv()

REQUIRED = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]


def connect():
    missing = [k for k in REQUIRED if not os.getenv(k)]
    if missing:
        raise SystemExit(f"Missing settings in .env: {', '.join(missing)}")
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
    )


if __name__ == "__main__":
    conn = connect()
    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE(), VERSION()")
        db_name, version = cur.fetchone()
    print(f"Connected to database {db_name} (server version {version})")
    conn.close()
