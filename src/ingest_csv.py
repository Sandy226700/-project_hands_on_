from ingest_common import run_ingestion

if __name__ == "__main__":
    run_ingestion("data/bank_transactions.csv", "stg_csv", ",")
