import pandas as pd
import numpy as np
import re
import tabula

class DebugExtractor:
    def process_dataframe(self, df: pd.DataFrame, statement_year: int, statement_month: int):
        df.columns = [str(x).upper() for x in df.columns]
        
        # Look for headers
        header_found = False
        if 'DESCRIPTION' in df.columns and 'MONTANT' in df.columns:
            header_found = True
        else:
            for i in range(min(5, len(df))):
                row_values = [str(x).upper() for x in df.iloc[i].values]
                if any('DESCRIPTION' in val for val in row_values) and any('MONTANT' in val for val in row_values):
                    df.columns = row_values
                    df = df.iloc[i + 1:].reset_index(drop=True)
                    header_found = True
                    break
        
        if not header_found:
            return pd.DataFrame()

        df_clean = df.copy()
        date_pattern = r'^(\d{2})\s+(\d{2})'
        desc_col = next((col for col in df_clean.columns if 'DESCRIPTION' in col), 'DESCRIPTION')
        amount_col = next((col for col in df_clean.columns if 'MONTANT' in col), 'MONTANT')

        print(f"Columns: {list(df_clean.columns)}")
        print(f"Desc col: {desc_col}, Amount col: {amount_col}")

        # LOGIC FROM STRATEGIES.PY
        extracted_dates = df_clean[desc_col].astype(str).str.extract(date_pattern)
        date_from_desc = extracted_dates[0].notna() & extracted_dates[1].notna()

        fallback_dates = pd.Series(index=df_clean.index, dtype=object)
        for col in df_clean.columns:
            if str(col).startswith('UNNAMED') and col != desc_col:
                col_dates = df_clean[col].astype(str).str.extract(date_pattern)
                mask = (~date_from_desc) & (col_dates[0].notna()) & (col_dates[1].notna())
                fallback_dates[mask] = col_dates[mask].apply(lambda row: (row[0], row[1]), axis=1)
                date_from_desc = date_from_desc | mask

        failed_idx = df_clean.index[~date_from_desc]
        print(f"Initial failed count: {len(failed_idx)}")
        
        if len(failed_idx) > 0:
            cols = list(df_clean.columns)
            for idx in failed_idx:
                vals = [str(df_clean.at[idx, c]).strip() if pd.notna(df_clean.at[idx, c]) else "" for c in cols]
                found = None
                for i in range(len(vals) - 1):
                    left = vals[i]
                    right = vals[i + 1]
                    if re.fullmatch(r"\d{1,2}", left) and re.fullmatch(r"\d{1,2}", right):
                        day = int(left)
                        month = int(right)
                        if 1 <= day <= 31 and 1 <= month <= 12:
                            found = (f"{day:02d}", f"{month:02d}")
                            break
                if found:
                    fallback_dates.at[idx] = found

        final_dates = extracted_dates.copy()
        for idx in fallback_dates[fallback_dates.notna()].index:
            final_dates.loc[idx, 0] = fallback_dates[idx][0]
            final_dates.loc[idx, 1] = fallback_dates[idx][1]

        valid_rows = final_dates[0].notna() & final_dates[1].notna()
        print(f"Valid rows after all fallbacks: {valid_rows.sum()}")
        
        if valid_rows.sum() == 0:
            print("\nSAMPLE FAILED ROWS:")
            for idx in failed_idx[:10]:
                print(f"Row {idx}: {list(df_clean.loc[idx])}")

        return df_clean[valid_rows]

pdf_path = "media/statements/2026/03/6000-juillet-2024.pdf"
dfs = tabula.read_pdf(pdf_path, pages='all', stream=True)
extractor = DebugExtractor()
for i, df in enumerate(dfs):
    print(f"\n--- DF {i} ---")
    res = extractor.process_dataframe(df, 2024, 7)
    if not res.empty:
        print(f"Captured {len(res)} rows from DF {i}")
