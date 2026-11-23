import csv
from pathlib import Path

from openpyxl import Workbook

csv_path = Path("data") / "bank_transactions.csv"
xlsx_path = Path("data") / "bank_transactions.xlsx"

if not csv_path.exists():
    raise SystemExit(f"{csv_path} not found. Run src/generate_files.py first.")

wb = Workbook()
ws = wb.active
ws.title = "transactions"

with open(csv_path, newline="") as f:
    reader = csv.DictReader(f)
    ws.append(reader.fieldnames)
    for row in reader:
        ws.append([
            row["transaction_id"],
            int(row["account_id"]),
            row["transaction_date"],
            row["transaction_type"],
            float(row["amount"]),
            int(row["branch_id"]),
        ])

wb.save(xlsx_path)
print(f"Created {xlsx_path} with {ws.max_row - 1} data rows")
