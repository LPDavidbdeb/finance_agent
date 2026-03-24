#!/usr/bin/env python
"""Test the new payment extraction functionality for Visa Desjardins PDFs."""

import os
import django

# Setup Django FIRST before any imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings.local')
django.setup()

import glob
import pandas as pd
from pathlib import Path

# Find all Visa Desjardins PDFs
pdf_dir = "/Users/Louis-Philippe/Documents/finance_agent/media/statements"
pdf_files = sorted(glob.glob(os.path.join(pdf_dir, "**/*.pdf"), recursive=True))

# Filter for Visa Desjardins files (starting with "6000" or "454033600")
visa_pdfs = [f for f in pdf_files if any(x in os.path.basename(f) for x in ["6000", "454033600"])][:3]

print(f"Testing {len(visa_pdfs)} Visa Desjardins statements\n")
print("=" * 80)

# Import after Django setup
from ai_core.extractors.strategies import VisaDesjardinsExtractor
from banking.extraction import get_statement_date_from_pdf
import tabula

extractor = VisaDesjardinsExtractor()
total_rows = 0
total_payments = 0

for pdf_path in visa_pdfs:
    filename = os.path.basename(pdf_path)

    try:
        # Get statement date
        year, month = get_statement_date_from_pdf(pdf_path)
        print(f"\n📄 {filename} (Year: {year}, Month: {month})")

        # Extract tables using tabula
        tables = tabula.read_pdf(pdf_path, pages='all', stream=True, silent=True)

        print(f"   Found {len(tables)} table(s) in PDF")

        payment_count_per_pdf = 0
        for i, table in enumerate(tables):
            if table.empty:
                continue

            result, _ = extractor.process_dataframe(table.copy(), year, month)

            if not result.empty:
                payment_rows = result[result['description'].astype(str).str.contains('PAIEMENT', case=False, na=False)]
                if not payment_rows.empty:
                    total_payments += len(payment_rows)
                    payment_count_per_pdf += len(payment_rows)
                    print(f"   ✅ Table {i}: Found {len(payment_rows)} PAYMENT row(s)")
                    for idx, row in payment_rows.iterrows():
                        print(f"      - {row['date'].date()}: {row['description'][:50]} | {row['amount']:.2f}")

                total_rows += len(result)

        if payment_count_per_pdf == 0:
            print(f"   ⚠️  No payment rows found")

    except Exception as e:
        print(f"\n❌ Error processing {filename}: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print(f"Summary: {total_payments} payment rows extracted from {len(visa_pdfs)} statements")
print(f"Total transaction rows: {total_rows}")

