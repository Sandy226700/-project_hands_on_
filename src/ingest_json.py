import json

from ingest_common import run_ingestion, validate_row


def read_json(path):
    with open(path) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON syntax: {exc}")
    if not isinstance(data, list):
        raise ValueError("JSON file must contain a list of records")
    rows = []
    for i, record in enumerate(data, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"record {i}: not a JSON object")
        rows.append(validate_row(record, f"record {i}"))
    return rows


if __name__ == "__main__":
    run_ingestion("data/bank_transactions.json", "stg_json", read_json)
