import re
import logging
import pandas as pd
import numpy as np
from .base import BasePDFExtractor

logger = logging.getLogger(__name__)


class VisaDesjardinsExtractor(BasePDFExtractor):
    def tabula_parameters(self) -> dict:
        return {'pages': 'all', 'stream': True}

    def _extract_payment_table(self, df: pd.DataFrame, statement_year: int, statement_month: int) -> tuple[
        pd.DataFrame, bool]:
        """
        Extracts only the payments.
        In Liability logic: Payments are NEGATIVE (decreases debt).
        """
        df.columns = [str(x).upper() for x in df.columns]

        header_found = 'DESCRIPTION' in df.columns and 'MONTANT' in df.columns
        if not header_found:
            for i in range(min(5, len(df))):
                row_values = [str(x).upper() for x in df.iloc[i].values]
                if any('DESCRIPTION' in val for val in row_values) and any('MONTANT' in val for val in row_values):
                    df.columns = row_values
                    df = df.iloc[i + 1:].reset_index(drop=True)
                    header_found = True
                    break

        if not header_found:
            return pd.DataFrame(columns=['date', 'description', 'amount', 'account_identifier']), False

        first_col = df.columns[0]
        desc_col = next((col for col in df.columns if 'DESCRIPTION' in col), None)
        amount_col = next((col for col in df.columns if 'MONTANT' in col), None)

        if not desc_col or not amount_col:
            return pd.DataFrame(columns=['date', 'description', 'amount', 'account_identifier']), False

        payments = []
        date_pattern = r'^(\d{2})\s(\d{2})'

        for idx, row in df.iterrows():
            desc_val = row[desc_col]
            if isinstance(desc_val, pd.Series):
                desc_val = desc_val.iloc[0] if len(desc_val) > 0 else ""
            desc = str(desc_val).strip()

            if 'PAIEMENT' not in desc.upper() and 'PRÉLÈVEMENT' not in desc.upper():
                continue

            first_col_val = row[first_col]
            if isinstance(first_col_val, pd.Series):
                first_col_val = first_col_val.iloc[0] if len(first_col_val) > 0 else ""
            first_col_str = str(first_col_val).strip()

            amount_val = row[amount_col]
            if isinstance(amount_val, pd.Series):
                amount_val = amount_val.iloc[0] if len(amount_val) > 0 else ""
            raw_amount = str(amount_val).strip()

            match = re.match(date_pattern, first_col_str)
            if match:
                tx_days, tx_months = int(match.group(1)), int(match.group(2))
                tx_years = statement_year - 1 if (statement_month == 1 and tx_months == 12) else statement_year

                amount_magnitude = raw_amount.replace('%', '').replace(' ', '').replace(',', '.').upper().replace('CR', '').replace('-', '').strip()

                try:
                    parsed_amount = float(amount_magnitude)
                    # FORCE NEGATIVE for payments (Liability reduction)
                    final_amount = -abs(parsed_amount)

                    payments.append({
                        'date': pd.Timestamp(year=tx_years, month=tx_months, day=tx_days),
                        'description': desc,
                        'amount': final_amount,
                        'account_identifier': 'CREDIT_CARD'
                    })
                except ValueError:
                    continue

        df_clean = pd.DataFrame(payments, columns=['date', 'description', 'amount', 'account_identifier'])
        return df_clean.dropna(subset=['date', 'amount']), False

    def _extract_regular_transactions(self, df: pd.DataFrame, statement_year: int, statement_month: int) -> tuple[
        pd.DataFrame, bool]:
        """
        Extracts regular purchases.
        In Liability logic: Purchases are POSITIVE (increases debt).
        """
        df.columns = [str(x).upper() for x in df.columns]

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
            return pd.DataFrame(columns=['date', 'description', 'amount', 'account_identifier']), False

        df_clean = df.copy()
        date_pattern = r'^(\d{2})\s(\d{2})'
        desc_col = next((col for col in df_clean.columns if 'DESCRIPTION' in col), 'DESCRIPTION')
        amount_col = next((col for col in df_clean.columns if 'MONTANT' in col), 'MONTANT')

        desc_upper = df_clean[desc_col].astype(str).str.upper()
        payment_mask = desc_upper.str.contains('PAIEMENT', na=False) | desc_upper.str.contains('PRÉLÈVEMENT', na=False)
        df_clean = df_clean[~payment_mask].reset_index(drop=True)

        extracted_dates = df_clean[desc_col].astype(str).str.extract(date_pattern)
        valid_rows = extracted_dates[0].notna() & extracted_dates[1].notna()
        extracted_dates = extracted_dates[valid_rows]

        tx_months = extracted_dates[1].astype(int)
        tx_days = extracted_dates[0].astype(int)
        tx_years = np.where((statement_month == 1) & (tx_months == 12), statement_year - 1, statement_year)

        df_clean['date'] = pd.to_datetime(dict(year=tx_years, month=tx_months, day=tx_days), errors='coerce')

        descriptions = df_clean[desc_col].astype(str).copy()
        descriptions = descriptions.str.replace(r'^\d{2}\s+\d{2}\s+\d{2}\s+\d{2}\s+', '', regex=True)
        descriptions = descriptions.str.replace(r'^\d{2}\s+\d{2}\s+', '', regex=True)
        descriptions = descriptions.str.replace(r'^\d{2}\s+', '', regex=True)
        df_clean['description'] = descriptions.str.strip()

        raw_amount = df_clean[amount_col].astype(str)
        
        # 1. Surgical CR detection: at the end of amount OR in the immediate next column
        has_cr = raw_amount.str.strip().str.endswith('CR') | raw_amount.str.strip().str.endswith('cr')
        
        try:
            amount_col_idx = df_clean.columns.get_loc(amount_col)
            if amount_col_idx + 1 < len(df_clean.columns):
                next_col_val = df_clean.iloc[:, amount_col_idx + 1].astype(str).str.strip()
                has_cr = has_cr | (next_col_val == 'CR') | (next_col_val == 'cr')
        except:
            pass

        # 2. Bonidollars hint: If there are bonidollars, it's NOT a refund (usually)
        boni_col = next((col for col in df_clean.columns if 'BONI' in col), None)
        if boni_col:
            has_boni = df_clean[boni_col].astype(str).str.contains('%', na=False)
            # If it has Boni, it's NOT a credit, even if we thought we saw CR
            has_cr = has_cr & ~has_boni

        has_minus = raw_amount.str.contains('-', regex=False)

        amount_magnitude = (
            raw_amount
            .str.replace('%', '', regex=False)
            .str.replace(' ', '', regex=False)
            .str.replace(',', '.', regex=False)
            .str.replace('CR', '', case=False, regex=True)
            .str.replace('-', '', regex=False)
            .str.strip()
        )
        parsed_amount = pd.to_numeric(amount_magnitude, errors='coerce')

        # LIABILITY LOGIC:
        # Regular Purchase (no CR) = Positive
        # Refund/Credit (CR) = Negative
        df_clean['amount'] = parsed_amount * np.where(has_cr | has_minus, -1, 1)
        df_clean['account_identifier'] = 'CREDIT_CARD'

        return df_clean[['date', 'description', 'amount', 'account_identifier']].dropna(subset=['date', 'amount']), False

    def process_dataframe(self, df: pd.DataFrame, statement_year: int, statement_month: int) -> tuple[
        pd.DataFrame, bool]:
        df_transactions, _ = self._extract_regular_transactions(df.copy(), statement_year, statement_month)
        df_payments, _ = self._extract_payment_table(df.copy(), statement_year, statement_month)
        df_merged = pd.concat([df_transactions, df_payments], ignore_index=True)
        return df_merged, False


class MasterCardWealthSimpleExtractor(BasePDFExtractor):
    def sort_debit_credit(self, df):
        credit_list, debit_list = [], []
        for amount in df["AMOUNT"]:
            amount_str = str(amount).strip()
            # If it starts with a dash (standard or special), it's a debit (outflow)
            if amount_str.startswith('–') or amount_str.startswith('-'):
                credit_list.append(None)
                debit_list.append(amount)
            else:
                # Otherwise it's a credit (inflow)
                credit_list.append(amount)
                debit_list.append(None)
        df["CREDIT"], df["DEBIT"] = credit_list, debit_list
        return df

    def clean_amount_col(self, cash_col_name_list, df):
        caracter_list = ["$", " "]
        for col_name in cash_col_name_list:
            amount_list = []
            for amount in df[col_name]:
                if pd.notna(amount) and amount != "":
                    amount = str(amount).strip()
                    # Handle "1 661,24 $" or "–1 661,24 $" or "1,661.24 $" (standard)
                    # For Wealthsimple, we want the positive magnitude in the DEBIT/CREDIT column
                    # because the final amount is calculated as CREDIT - DEBIT.
                    amount = amount.replace('–', '').replace('-', '')
                    
                    # 1. Remove currency and spaces
                    for caracter in caracter_list:
                        amount = amount.replace(caracter, "")
                    
                    # 2. If there's a comma AND no dot, replace comma with dot
                    if ',' in amount and '.' not in amount:
                        amount = amount.replace(',', '.')
                    # 3. If there's a comma AND a dot, it's thousands (e.g., 1,234.56), so strip comma
                    elif ',' in amount and '.' in amount:
                        amount = amount.replace(',', '')
                    
                    try:
                        amount = float(amount)
                    except:
                        try:
                            # Try again stripping leading non-digit chars if float fails
                            amount = float(re.sub(r'^[^\d-]+', '', amount))
                        except:
                            amount = 0.0
                else:
                    amount = 0.0
                amount_list.append(amount)
            df[col_name] = amount_list
        return df

    def process_dataframe(self, df: pd.DataFrame, statement_year: int, statement_month: int) -> tuple[pd.DataFrame, bool]:
        if len(df.columns) == 4:
            if df.columns.to_list() == ['Activity - Current period', 'Unnamed: 0', 'Unnamed: 1', 'Unnamed: 2']:
                date_operation_desc_execution_list = df['Activity - Current period'][1:].to_list()
                date_operation_desc_execution_list = [
                    (str(x).split()[0], str(x).split()[1], " ".join(str(x).split()[2:]).split("(")) for x in
                    date_operation_desc_execution_list if len(str(x).split()) >= 3]
                date_operation_desc_execution_list = [(x[0], x[1], x[2][0], x[2][1] if len(x[2]) > 1 else "") for x in
                                                      date_operation_desc_execution_list]

                date = [x[0] for x in date_operation_desc_execution_list]
                desc = [x[2] for x in date_operation_desc_execution_list]

                temp_df = pd.DataFrame({
                    "Date": date, "Description": desc,
                    "Charged ($)": df['Unnamed: 0'][1:len(date) + 1].to_list(),
                    "Credit ($)": df['Unnamed: 1'][1:len(date) + 1].to_list()
                })

                temp_df = self.clean_amount_col(["Charged ($)", "Credit ($)"], temp_df)
                temp_df['date'] = pd.to_datetime(temp_df['Date'], format='%Y-%m-%d', errors='coerce')
                # Wealthsimple is an ASSET (Cash Flow logic): Inflow (+) / Outflow (-)
                temp_df['amount'] = temp_df['Credit ($)'] - temp_df['Charged ($)']
                temp_df['description'] = temp_df['Description']
                temp_df['account_identifier'] = 'SAVINGS'
                return temp_df[['date', 'description', 'amount', 'account_identifier']].dropna(subset=['date']), False
            else:
                col_name = ["DATE", "DESCRIPTION", "AMOUNT", "BALANCE"]
                first = pd.DataFrame({k: [v] for k, v in zip(col_name, df.columns.to_list())})
                df.columns = col_name
                stacked_df = pd.concat([first, df], axis=0, ignore_index=True)

                stacked_df["DATE"] = pd.to_datetime(stacked_df["DATE"], format='%Y-%m-%d', errors='coerce')
                stacked_df = self.sort_debit_credit(stacked_df)
                stacked_df = self.clean_amount_col(["CREDIT", "DEBIT", "BALANCE"], stacked_df)

                stacked_df['amount'] = stacked_df['CREDIT'] - stacked_df['DEBIT']
                stacked_df['description'] = stacked_df['DESCRIPTION']
                stacked_df['date'] = stacked_df['DATE']
                stacked_df['account_identifier'] = 'SAVINGS'
                return stacked_df[['date', 'description', 'amount', 'account_identifier']].dropna(subset=['date']), False

        elif len(df.columns) == 5:
            col_name = ["DATE", "POSTED DATE", "DESCRIPTION", "AMOUNT", "BALANCE"]
            ligne_a_insérée = [str(x).replace(".1", "") for x in df.columns.to_list()]
            df.columns = col_name
            new_df = pd.DataFrame(dict(zip(col_name, ligne_a_insérée)), index=[0])
            df = pd.concat([df, new_df], ignore_index=True)

            df = self.sort_debit_credit(df)
            df = self.clean_amount_col(["CREDIT", "DEBIT", "BALANCE"], df)
            df['date'] = pd.to_datetime(df['DATE'], format='%Y-%m-%d', errors='coerce')

            df['amount'] = df['CREDIT'] - df['DEBIT']
            df['description'] = df['DESCRIPTION']
            df['account_identifier'] = 'SAVINGS'
            return df[['date', 'description', 'amount', 'account_identifier']].dropna(subset=['date']), False

        return pd.DataFrame(columns=['date', 'description', 'amount', 'account_identifier']), False


class CompteDesjardinsExtractor(BasePDFExtractor):
    def tabula_parameters(self) -> dict:
        return {'pages': 'all', 'stream': True}

    def to_date(self, date_str, statement_year, statement_month):
        from datetime import datetime
        # Extended dictionary to support both full and short French month names
        date_dict = {
            "JAN": 1, "JANV": 1, "JANVIER": 1,
            "FEB": 2, "FEV": 2, "FÉV": 2, "FÉVR": 2, "FÉVRIER": 2,
            "MAR": 3, "MARS": 3,
            "APR": 4, "AVR": 4, "AVRI": 4, "AVRIL": 4,
            "MAY": 5, "MAI": 5,
            "JUN": 6, "JUIN": 6,
            "JUL": 7, "JUIL": 7, "JUILLET": 7,
            "AUG": 8, "AOU": 8, "AOÛ": 8, "AOÛT": 8,
            "SEP": 9, "SEPT": 9, "SEPTEMBRE": 9,
            "OCT": 10, "OCTO": 10, "OCTOBRE": 10,
            "NOV": 11, "NOVE": 11, "NOVEMBRE": 11,
            "DEC": 12, "DÉC": 12, "DÉCE": 12, "DÉCEMBRE": 12
        }

        if isinstance(date_str, str) and date_str.strip() != "":
            parts = date_str.strip().split()
            if len(parts) >= 2:
                try:
                    d = int(parts[0])
                    m_str = parts[1].upper().replace('.', '')
                    m = date_dict.get(m_str)
                    if m:
                        year = statement_year - 1 if (statement_month == 1 and m == 12) else statement_year
                        return datetime(year, m, d)
                except Exception:
                    pass
            elif len(parts) == 1:
                # Fallback: only day provided (e.g. "31")
                try:
                    d = int(parts[0])
                    return datetime(statement_year, statement_month, d)
                except:
                    pass
        return None

    def _clean_amount(self, val):
        if pd.isna(val) or val == "" or val == "None":
            return 0.0
        s = str(val).strip().replace(' ', '').replace('$', '').replace('\xa0', '')
        if not s:
            return 0.0
        # Handle French decimal comma
        if ',' in s and '.' not in s:
            s = s.replace(',', '.')
        elif ',' in s and '.' in s:
            s = s.replace(',', '')
        
        # Handle 'CR' suffix
        is_credit = 'CR' in s.upper()
        s = s.upper().replace('CR', '').replace('-', '')
        
        try:
            magnitude = float(s)
            return -magnitude if is_credit else magnitude
        except ValueError:
            # Try to extract the first number found in string
            import re
            match = re.search(r'[\d.]+', s)
            if match:
                try:
                    magnitude = float(match.group())
                    return -magnitude if is_credit else magnitude
                except:
                    pass
        return 0.0

    def process_dataframe(self, df: pd.DataFrame, statement_year: int, statement_month: int) -> tuple[pd.DataFrame, bool]:
        df_work = df.copy()
        # Clean columns: uppercase, no newlines, no whitespace
        df_work.columns = [str(c).upper().replace('\r', ' ').replace('\n', ' ').strip() for c in df_work.columns]
        
        # 1. Identify key columns
        date_col = next((c for c in df_work.columns if 'DATE' in c), None)
        desc_col = next((c for c in df_work.columns if 'DESCRIPTION' in c or 'UNNAMED: 0' in c), None)
        # If both Unnamed: 0 and Description exist, prefer Description for text, but watch for shifts
        if 'DESCRIPTION' in df_work.columns and 'UNNAMED: 0' in df_work.columns:
            desc_col = 'UNNAMED: 0' # In Desjardins PDFs, Unnamed: 0 often holds the actual text
            
        retrait_col = next((c for c in df_work.columns if 'RETRAIT' in c or 'CHARGED' in c), None)
        depot_col = next((c for c in df_work.columns if 'DÉPÔT' in c or 'DEPOT' in c or 'CREDIT' in c), None)
        frais_col = next((c for c in df_work.columns if 'FRAIS' in c), None)
        transaction_col = next((c for c in df_work.columns if 'TRANSACTION' in c), None)
        
        # 2. Extract rows
        rows = []
        df_list = df_work.to_dict('records')
        i = 0
        while i < len(df_list):
            row = df_list[i]
            
            # Try to find a date in ANY column
            parsed_date = None
            date_found_in_col = None
            
            for c in df_work.columns:
                parsed_date = self.to_date(str(row[c]), statement_year, statement_month)
                if parsed_date:
                    date_found_in_col = c
                    break
            
            if not parsed_date:
                i += 1
                continue
                
            # Description discovery
            description = "Unknown"
            text_candidates = []
            for c in df_work.columns:
                if c == date_found_in_col: continue
                val = str(row[c]).strip()
                if val and val.lower() != 'nan':
                    alpha_count = sum(1 for char in val if char.isalpha())
                    text_candidates.append((c, val, alpha_count))
            text_candidates.sort(key=lambda x: x[2], reverse=True)
            if text_candidates:
                if text_candidates[0][2] <= 3 and len(text_candidates) > 1 and text_candidates[1][2] > 0:
                    description = f"{text_candidates[0][1]} {text_candidates[1][1]}".strip()
                else:
                    description = text_candidates[0][1]
            
            if any(k in description.upper() for k in ['SOLDE REPORTÉ', 'SOLDE REPORTER']):
                i += 1
                continue

            # Amounts discovery
            retrait = self._clean_amount(row.get(retrait_col)) if retrait_col else 0.0
            depot = self._clean_amount(row.get(depot_col)) if depot_col else 0.0
            frais = self._clean_amount(row.get(frais_col)) if frais_col else 0.0
            
            # --- LOOK AHEAD for multi-line transactions ---
            # If all amounts are 0 and there's a next row, check if the next row has the amount
            if retrait == 0 and depot == 0 and frais == 0 and i + 1 < len(df_list):
                next_row = df_list[i+1]
                # A row is a candidate if it doesn't have its own date
                has_own_date = any(self.to_date(str(next_row[c]), statement_year, statement_month) for c in df_work.columns)
                
                if not has_own_date:
                    # Look for amounts in the next row
                    n_retrait = self._clean_amount(next_row.get(retrait_col)) if retrait_col else 0.0
                    n_depot = self._clean_amount(next_row.get(depot_col)) if depot_col else 0.0
                    n_frais = self._clean_amount(next_row.get(frais_col)) if frais_col else 0.0
                    
                    if n_retrait != 0 or n_depot != 0 or n_frais != 0:
                        retrait, depot, frais = n_retrait, n_depot, n_frais
                        # Also merge description if the next row has text
                        next_text = " ".join([str(next_row[c]) for c in df_work.columns if str(next_row[c]).lower() != 'nan' and not str(next_row[c]).replace('.','').isdigit()])
                        if len(next_text.strip()) > 2:
                            description = f"{description} {next_text.strip()}".strip()
                        i += 1 # Consume the next row
                    else:
                        # Search the entire next row for ANY number if standard cols are empty
                        for c in df_work.columns:
                            val = self._clean_amount(next_row[c])
                            if val != 0:
                                # Heuristic: skip if it's the last column (likely SOLDE)
                                if list(df_work.columns).index(c) == len(df_work.columns) - 1:
                                    continue
                                if val > 0: depot = val
                                else: retrait = abs(val)
                                # Merge text from next row
                                next_text = " ".join([str(next_row[col]) for col in df_work.columns if col != c and str(next_row[col]).lower() != 'nan'])
                                description = f"{description} {next_text.strip()}".strip()
                                i += 1 # Consume
                                break

            # If still 0, look for ANY number in current row
            if retrait == 0 and depot == 0 and frais == 0:
                for c in df_work.columns:
                    if c == date_found_in_col: continue
                    val = self._clean_amount(row[c])
                    if val != 0:
                        if list(df_work.columns).index(c) == len(df_work.columns) - 1:
                            continue
                        if val > 0: depot = val
                        else: retrait = abs(val)
                        break

            # ASSET logic: Inflow (+) / Outflow (-)
            amount = depot - retrait - frais
            
            # Skip purely informational $0.00 transactions
            if amount == 0:
                i += 1
                continue

            rows.append({
                'date': parsed_date,
                'description': description,
                'amount': amount,
                'account_identifier': 'SAVINGS' if any(k in description.upper() for k in ['CELI', 'EPARGNE']) else 'CHECKING'
            })
            i += 1

        res_df = pd.DataFrame(rows)
        if res_df.empty:
            return pd.DataFrame(columns=['date', 'description', 'amount', 'account_identifier']), False
            
        return res_df, False



class TangerineExtractor(BasePDFExtractor):
    OUTPUT_COLUMNS = ['date', 'description', 'amount', 'account_number', 'inferred_product_type']
    _DEFAULT_PRODUCT_TYPE = 'CHECKING'
    _HEADER_RE = re.compile(r'Détails\s+-\s+.+?\s+-\s+(\d+)', re.IGNORECASE)
    _BALANCE_MARKERS = frozenset(["solde d'ouverture", 'solde'])

    def tabula_parameters(self) -> dict:
        return {}

    def extract(self, pdf_path: str, statement_year: int, statement_month: int) -> tuple[pd.DataFrame, bool]:
        import pdfplumber
        try:
            product_types = self._pass1_infer_product_types(pdf_path, pdfplumber)
            all_dfs = self._pass2_extract_from_text(pdf_path, pdfplumber, product_types)
            if not all_dfs:
                return pd.DataFrame(columns=self.OUTPUT_COLUMNS), False
            combined = pd.concat(all_dfs, ignore_index=True)
            return combined[self.OUTPUT_COLUMNS], False
        except Exception as e:
            logger.exception(f"[TangerineExtractor] Extraction failed: {e}")
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS), False

    def _pass1_infer_product_types(self, pdf_path: str, pdfplumber_module) -> dict:
        product_types = {}
        with pdfplumber_module.open(pdf_path) as pdf:
            for page in pdf.pages[:2]:
                text = page.extract_text() or ''
                if "coup d'oeil" not in text.lower():
                    continue
                for line in text.split('\n'):
                    acct_match = re.search(r'\b(\d{5,12})\b', line)
                    if not acct_match:
                        continue
                    account_number = acct_match.group(1)
                    line_lower = line.lower()
                    if 'celi' in line_lower:
                        product_types[account_number] = 'INVESTMENT'
                    elif 'cpg' in line_lower:
                        product_types[account_number] = 'INVESTMENT'
                    elif 'épargne' in line_lower or 'epargne' in line_lower:
                        product_types[account_number] = 'SAVINGS'
                    elif 'chèque' in line_lower or 'cheque' in line_lower:
                        product_types[account_number] = 'CHECKING'
                break
        return product_types

    def _pass2_extract_from_text(self, pdf_path: str, pdfplumber_module, product_types: dict) -> list:
        with pdfplumber_module.open(pdf_path) as pdf:
            full_text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
        sections = list(self._HEADER_RE.finditer(full_text))
        if not sections:
            return []
        all_dfs = []
        for i, match in enumerate(sections):
            account_number = match.group(1)
            section_start = match.end()
            section_end = sections[i + 1].start() if i + 1 < len(sections) else len(full_text)
            section_text = full_text[section_start:section_end]
            df = self._parse_section_text(section_text, account_number, product_types)
            if df is not None and not df.empty:
                all_dfs.append(df)
        return all_dfs

    def _parse_section_text(self, text: str, account_number: str, product_types: dict):
        product_type = product_types.get(account_number, self._DEFAULT_PRODUCT_TYPE)
        _MONEY = r'(?:[\d\u00a0\u202f ]+,\d{2})'
        TX_RE = re.compile(r'^(\d{2})\.(\d{2})\.(\d{4})\s+(.+)\s+(' + _MONEY + r')\s+(' + _MONEY + r')\s*$')

        def _parse_fr(s: str) -> float:
            return float(s.replace('\u00a0', '').replace('\u202f', '').replace(' ', '').replace(',', '.'))

        parsed = []
        for line in text.split('\n'):
            m = TX_RE.match(line.strip())
            if not m: continue
            try:
                tx_date = pd.Timestamp(year=int(m.group(3)), month=int(m.group(2)), day=int(m.group(1)))
            except ValueError: continue
            parsed.append((tx_date, m.group(4).strip(), m.group(5), m.group(6)))

        if not parsed: return None
        rows, prev_balance = [], None
        for tx_date, description, raw_amount, raw_balance in parsed:
            balance = _parse_fr(raw_balance)
            if description.lower() in self._BALANCE_MARKERS:
                prev_balance = balance
                continue
            magnitude = _parse_fr(raw_amount)
            # ASSET logic: Inflow (+) / Outflow (-)
            sign = 1.0 if prev_balance is not None and round(balance - prev_balance, 4) >= 0 else -1.0
            prev_balance = balance
            rows.append({'date': tx_date, 'description': description, 'amount': magnitude * sign, 'account_number': account_number, 'inferred_product_type': product_type})
        return pd.DataFrame(rows)

    def process_dataframe(self, df: pd.DataFrame, statement_year: int, statement_month: int) -> tuple[pd.DataFrame, bool]:
        raise NotImplementedError("TangerineExtractor overrides extract() directly.")
