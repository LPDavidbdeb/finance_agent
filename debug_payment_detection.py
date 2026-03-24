#!/usr/bin/env python
"""Debug payment detection in Visa PDFs."""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings.local')
django.setup()

import glob
import pandas as pd
import tabula

# Find a recent PDF
pdf_dir = "/Users/Louis-Philippe/Documents/finance_agent/media/statements"
pdf_files = glob.glob(os.path.join(pdf_dir, "**/*décembre-2024.pdf"), recursive=True)

if not pdf_files:
    print("December 2024 PDF not found, looking for any 6000-*.pdf...")
    pdf_files = glob.glob(os.path.join(pdf_dir, "**/*6000*.pdf"), recursive=True)

if pdf_files:
    pdf_path = pdf_files[0]
    print(f"Analyzing: {pdf_path}\n")

    # Extract tables
    tables = tabula.read_pdf(pdf_path, pages='all', stream=True, silent=True)

    for i, table in enumerate(tables):
        print(f"\n{'=' * 80}")
        print(f"TABLE {i}")
        print(f"{'=' * 80}")
        print(f"Shape: {table.shape}")
        print(f"Columns: {table.columns.tolist()}")

        # Look for PAIEMENT in any column
        has_paiement = False
        for col in table.columns:
            if table[col].astype(str).str.contains('PAIEMENT', case=False, na=False).any():
                has_paiement = True
                matching_rows = table[table[col].astype(str).str.contains('PAIEMENT', case=False, na=False)]
                print(f"\n✅ Found PAIEMENT in column '{col}':")
                print(matching_rows[[c for c in table.columns if c == col or 'MONTANT' in str(c) or i == 0]].to_string())
                break

        if not has_paiement:
            print("\n❌ No PAIEMENT found in this table")

        # Show first few rows
        if not table.empty:
            print(f"\nFirst 2 rows:")
            print(table.head(2).to_string())
else:
    print("No Visa PDFs found!")

