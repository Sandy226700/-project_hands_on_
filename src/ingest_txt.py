from ingest_common import read_delimited, run_ingestion


def read_txt(path):
    return read_delimited(path, "|")


if __name__ == "__main__":
    run_ingestion("data/bank_transactions.txt", "stg_txt", read_txt)
