import tabula
import pandas as pd

pdf_path = "media/statements/2026/03/6000-juillet-2024.pdf"
print(f"Reading {pdf_path} with Tabula...")

dfs = tabula.read_pdf(pdf_path, pages='all', stream=True)
for i, df in enumerate(dfs):
    print(f"\n--- Dataframe {i} ---")
    print(df.head(20).to_string())
