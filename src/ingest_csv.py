from ingest_common import read_delimited, run_ingestion


def read_csv(path):
    return read_delimited(path, ",")


if __name__ == "__main__":
    run_ingestion("data/bank_transactions.csv", "stg_csv", read_csv)
