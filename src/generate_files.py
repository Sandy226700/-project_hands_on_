import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

NUM_RECORDS = 1000
TYPES = ["DEPOSIT", "WITHDRAWAL", "TRANSFER", "UPI"]
COLUMNS = ["transaction_id", "account_id", "transaction_date",
           "transaction_type", "amount", "branch_id"]

data_dir = Path("data")
data_dir.mkdir(exist_ok=True)

start = date(2026, 11, 1)

records = []
for i in range(1, NUM_RECORDS + 1):
    records.append({
        "transaction_id": f"T{i:06d}",
        "account_id": random.randint(1001, 1100),
        "transaction_date": (start + timedelta(days=random.randint(0, 22))).isoformat(),
        "transaction_type": random.choice(TYPES),
        "amount": round(random.uniform(100, 50000), 2),
        "branch_id": random.randint(1, 10),
    })

# CSV: comma separated, with a header row
with open(data_dir / "bank_transactions.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(records)

# TXT: pipe-delimited, with a header row
with open(data_dir / "bank_transactions.txt", "w") as f:
    f.write("|".join(COLUMNS) + "\n")
    for r in records:
        f.write("|".join(str(r[c]) for c in COLUMNS) + "\n")

# JSON: a list of records
with open(data_dir / "bank_transactions.json", "w") as f:
    json.dump(records, f, indent=2)

print(f"Created {len(records)} records in 3 files inside {data_dir}/")
