import csv
from collections import Counter
from pathlib import Path

from fpdf import FPDF

csv_path = Path("data") / "bank_transactions.csv"
pdf_path = Path("data") / "account_statement.pdf"

if not csv_path.exists():
    raise SystemExit(f"{csv_path} not found. Run src/generate_files.py first.")

with open(csv_path, newline="") as f:
    rows = list(csv.DictReader(f))

# Pick the account with the most transactions (lowest account_id wins a tie)
counts = Counter(r["account_id"] for r in rows)
account_id = max(sorted(counts), key=counts.get)

txns = sorted(
    (r for r in rows if r["account_id"] == account_id),
    key=lambda r: (r["transaction_date"], r["transaction_id"]),
)

pdf = FPDF()
pdf.add_page()

pdf.set_font("Helvetica", "B", 16)
pdf.cell(0, 10, "Account Statement", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", size=11)
pdf.cell(0, 8, f"Account number: {account_id}", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 8, f"Number of transactions: {len(txns)}", new_x="LMARGIN", new_y="NEXT")
pdf.ln(4)

headers = ["Transaction ID", "Date", "Type", "Amount", "Branch"]
widths = [35, 35, 40, 45, 30]

pdf.set_font("Helvetica", "B", 10)
for h, w in zip(headers, widths):
    pdf.cell(w, 8, h, border=1)
pdf.ln()

pdf.set_font("Helvetica", size=10)
for r in txns:
    values = [
        r["transaction_id"],
        r["transaction_date"],
        r["transaction_type"],
        f"{float(r['amount']):,.2f}",
        r["branch_id"],
    ]
    for v, w in zip(values, widths):
        pdf.cell(w, 8, v, border=1)
    pdf.ln()

pdf.output(str(pdf_path))
print(f"Created {pdf_path} for account {account_id} with {len(txns)} transactions")
