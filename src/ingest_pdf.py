import re

import pdfplumber

from ingest_common import run_ingestion, validate_row

EXPECTED_HEADER = ["Transaction ID", "Date", "Type", "Amount", "Branch"]


def clean(cell):
    return "" if cell is None else " ".join(str(cell).split())


def read_pdf(path):
    try:
        pdf = pdfplumber.open(path)
    except Exception as exc:
        raise ValueError(f"cannot open PDF: {exc}")

    with pdf:
        text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        if not text.strip():
            raise ValueError("PDF has no extractable text")

        account = re.search(r"Account number:\s*(\d+)", text)
        stated = re.search(r"Number of transactions:\s*(\d+)", text)
        if not account:
            raise ValueError("account number not found in PDF header")
        if not stated:
            raise ValueError("transaction count not found in PDF header")
        account_id = account.group(1)
        stated_count = int(stated.group(1))

        rows = []
        n = 0
        for page in pdf.pages:
            for table in page.extract_tables():
                for raw in table:
                    cells = [clean(c) for c in raw]
                    if cells and cells[0] == EXPECTED_HEADER[0]:
                        if cells != EXPECTED_HEADER:
                            raise ValueError(f"unexpected table header: {cells}")
                        continue
                    if not any(cells):
                        continue
                    n += 1
                    if len(cells) != len(EXPECTED_HEADER):
                        raise ValueError(
                            f"statement row {n}: expected {len(EXPECTED_HEADER)} cells, found {len(cells)}")
                    record = {
                        "transaction_id": cells[0],
                        "account_id": account_id,
                        "transaction_date": cells[1],
                        "transaction_type": cells[2],
                        "amount": cells[3].replace(",", ""),
                        "branch_id": cells[4],
                    }
                    rows.append(validate_row(record, f"statement row {n}"))

    if n == 0:
        raise ValueError("no transaction table found in PDF")
    if len(rows) != stated_count:
        raise ValueError(
            f"control total mismatch: statement says {stated_count} transactions, extracted {len(rows)}")
    return rows


if __name__ == "__main__":
    run_ingestion("data/account_statement.pdf", "stg_pdf", read_pdf)
