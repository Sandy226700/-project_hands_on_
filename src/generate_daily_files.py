import csv
import random
from pathlib import Path

COLUMNS = ["transaction_id", "account_id", "transaction_date",
           "transaction_type", "amount", "branch_id"]
TYPES = ["DEPOSIT", "WITHDRAWAL", "TRANSFER", "UPI"]
INITIAL_CSV = Path("data") / "bank_transactions.csv"
OUT_DIR = Path("data") / "daily"

rng = random.Random(2026)


def make_row(n, day):
    return {
        "transaction_id": f"N{n:06d}",
        "account_id": rng.randint(1001, 1100),
        "transaction_date": day,
        "transaction_type": rng.choice(TYPES),
        "amount": f"{rng.uniform(100, 50000):.2f}",
        "branch_id": rng.randint(1, 10),
    }


def corrected(row):
    """Same transaction, different amount (1000 more, or 1000 less near the limit)."""
    amount = float(row["amount"])
    new_amount = amount + 1000 if amount <= 49000 else amount - 1000
    changed = dict(row)
    changed["amount"] = f"{new_amount:.2f}"
    return changed


def write_file(day, rows):
    path = OUT_DIR / f"transactions_{day}.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Created {path} with {len(rows)} rows")


def main():
    if not INITIAL_CSV.exists():
        raise SystemExit(f"{INITIAL_CSV} not found. Run src/generate_files.py first.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(INITIAL_CSV, newline="") as f:
        initial = {r["transaction_id"]: r for r in csv.DictReader(f)}

    # Day 1: 50 new rows
    day1 = [make_row(n, "2026-12-01") for n in range(1, 51)]

    # Day 2: 40 new, 5 late arrivals (dated day 1), 3 identical resends, 2 corrections
    new2 = [make_row(n, "2026-12-02") for n in range(51, 91)]
    late2 = [make_row(n, "2026-12-01") for n in range(91, 96)]
    resend2 = [dict(r) for r in day1[0:3]]
    corr2 = [corrected(day1[3]), corrected(day1[4])]
    day2 = new2 + late2 + resend2 + corr2
    rng.shuffle(day2)

    # Day 3: 30 new, 1 identical resend of a day 2 row, 1 correction of an initial-load row
    new3 = [make_row(n, "2026-12-03") for n in range(96, 126)]
    resend3 = [dict(new2[0])]
    corr3 = [corrected(initial["T000001"])]
    day3 = new3 + resend3 + corr3
    rng.shuffle(day3)

    write_file("2026-12-01", day1)
    write_file("2026-12-02", day2)
    write_file("2026-12-03", day3)

    print("Corrections designed into the files (old amount -> new amount):")
    for old, new in [(day1[3], corr2[0]), (day1[4], corr2[1]),
                     (initial["T000001"], corr3[0])]:
        print(f"  {old['transaction_id']}: {old['amount']} -> {new['amount']}")
    print("Expected when loaded in order: day 1: 50 new; "
          "day 2: 45 new, 3 unchanged, 2 corrected; "
          "day 3: 30 new, 1 unchanged, 1 corrected; history: 1125 rows")


if __name__ == "__main__":
    main()
