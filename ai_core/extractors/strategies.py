import re
import pandas as pd
import numpy as np
from .base import BasePDFExtractor


class VisaDesjardinsExtractor(BasePDFExtractor):
    def tabula_parameters(self) -> dict:
        return {'pages': 'all', 'stream': True}

    def _extract_payment_table(self, df: pd.DataFrame, statement_year: int, statement_month: int) -> tuple[
        pd.DataFrame, bool]:
        """
        NEW LOGIC: Extracts only the payments using the 100% success rate test logic.
        Looks specifically at the first column for the date.
        """
        df.columns = [str(x).upper() for x in df.columns]

        header_found = False
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
            # Get description
            desc_val = row[desc_col]
            if isinstance(desc_val, pd.Series):
                desc_val = desc_val.iloc[0] if len(desc_val) > 0 else ""
            desc = str(desc_val).strip()

            if 'PAIEMENT' not in desc.upper() and 'PRÉLÈVEMENT' not in desc.upper():
                continue

            # Get first column value
            first_col_val = row[first_col]
            if isinstance(first_col_val, pd.Series):
                first_col_val = first_col_val.iloc[0] if len(first_col_val) > 0 else ""
            first_col_str = str(first_col_val).strip()

            # Get amount
            amount_val = row[amount_col]
            if isinstance(amount_val, pd.Series):
                amount_val = amount_val.iloc[0] if len(amount_val) > 0 else ""
            raw_amount = str(amount_val).strip()

            # Extract using first column
            match = re.match(date_pattern, first_col_str)
            if match:
                tx_days, tx_months = int(match.group(1)), int(match.group(2))

                # Apply standard rollover logic
                tx_years = statement_year - 1 if (statement_month == 1 and tx_months == 12) else statement_year

                # Clean amount using the same logic as your regular transactions
                has_cr = bool(re.search(r'\bCR\b', raw_amount, re.IGNORECASE))
                has_minus = '-' in raw_amount
                amount_magnitude = raw_amount.replace('%', '').replace(' ', '').replace(',', '.').upper().replace('CR',
                                                                                                                  '').replace(
                    '-', '').strip()

                try:
                    parsed_amount = float(amount_magnitude)
                    # Payments (CR or -) = positive amount (reduces liability)
                    final_amount = parsed_amount * (-1 if has_cr or has_minus else 1)

                    payments.append({
                        'date': pd.Timestamp(year=tx_years, month=tx_months, day=tx_days),
                        'description': desc,
                        'amount': final_amount,
                        'account_identifier': 'CREDIT_CARD'
                    })
                except ValueError:
                    continue

        df_clean = pd.DataFrame(payments, columns=['date', 'description', 'amount', 'account_identifier'])
        df_transactions = df_clean[['date', 'description', 'amount', 'account_identifier']].dropna(
            subset=['date', 'amount'])

        return df_transactions, False

    def _extract_regular_transactions(self, df: pd.DataFrame, statement_year: int, statement_month: int) -> tuple[
        pd.DataFrame, bool]:
        """
        YOUR EXACT WORKING SCRIPT: Extracts regular purchases.
        Unmodified and perfectly intact.
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

        # Extract dates from description column (primary method for regular transactions)
        extracted_dates = df_clean[desc_col].astype(str).str.extract(date_pattern)
        valid_rows = extracted_dates[0].notna() & extracted_dates[1].notna()

        extracted_dates = extracted_dates[valid_rows]

        # Rollover logic: If statement is in January and transaction is in December, it's from previous year
        tx_months = extracted_dates[1].astype(int)
        tx_days = extracted_dates[0].astype(int)
        tx_years = np.where((statement_month == 1) & (tx_months == 12), statement_year - 1, statement_year)

        df_clean['date'] = pd.to_datetime(
            dict(year=tx_years, month=tx_months, day=tx_days),
            errors='coerce'
        )

        # Clean description: Remove date patterns to get the actual description text
        # Handles "DD MM DESCRIPTION", "DD MM DD MM DESCRIPTION", and "DD DESCRIPTION" (payment rows) formats
        descriptions = df_clean[desc_col].astype(str).copy()
        # First try removing double date pattern (DD MM DD MM)
        descriptions = descriptions.str.replace(r'^\d{2}\s+\d{2}\s+\d{2}\s+\d{2}\s+', '', regex=True)
        # Then remove single date pattern (DD MM)
        descriptions = descriptions.str.replace(r'^\d{2}\s+\d{2}\s+', '', regex=True)
        # Finally remove leading single day for payment rows (DD PAIEMENT...)
        descriptions = descriptions.str.replace(r'^\d{2}\s+', '', regex=True)
        df_clean['description'] = descriptions.str.strip()

        raw_amount = df_clean[amount_col].astype(str)
        has_cr = raw_amount.str.contains(r'\bCR\b', case=False, regex=True)
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

        # Payments (CR or -) = positive amount (reduces liability)
        # Purchases (no CR) = negative amount (increases liability)
        df_clean['amount'] = parsed_amount * np.where(has_cr | has_minus, -1, 1)
        df_clean['account_identifier'] = 'CREDIT_CARD'

        return df_clean[['date', 'description', 'amount', 'account_identifier']].dropna(
            subset=['date', 'amount']), False

    def process_dataframe(self, df: pd.DataFrame, statement_year: int, statement_month: int) -> tuple[
        pd.DataFrame, bool]:
        """
        The orchestrator: Runs both extractions independently and merges the DataFrames.
        """
        # 1. Extract regular transactions into a DataFrame
        df_transactions, _ = self._extract_regular_transactions(df.copy(), statement_year, statement_month)

        # 2. Extract payments into a DataFrame
        df_payments, _ = self._extract_payment_table(df.copy(), statement_year, statement_month)

        # 3. Merge the two DataFrames safely
        df_merged = pd.concat([df_transactions, df_payments], ignore_index=True)

        return df_merged, False


class MasterCardWealthSimpleExtractor(BasePDFExtractor):
    def sort_debit_credit(self, df):
        credit_list, debit_list = [], []
        for amount in df["AMOUNT"]:
            if str(amount)[0] != "$":
                credit_list.append(None)
                debit_list.append(amount)
            else:
                credit_list.append(amount)
                debit_list.append(None)
        df["CREDIT"], df["DEBIT"] = credit_list, debit_list
        return df

    def clean_amount_col(self, cash_col_name_list, df):
        caracter_list = ["$", ",", '-']
        for col_name in cash_col_name_list:
            amount_list = []
            for amount in df[col_name]:
                if pd.notna(amount) and amount != "":
                    amount = str(amount)
                    for caracter in caracter_list:
                        amount = amount.replace(caracter, "")
                    try:
                        amount = float(amount)
                    except:
                        try:
                            amount = float(amount[1:])
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
        date_dict = {
            "MAI": 5, 'JUN': 6, 'JUL': 7, 'AOU': 8, 'SEP': 9, 'OCT': 10,
            'NOV': 11, 'DEC': 12, 'JAN': 1, "FEV": 2, "MAR": 3, "AVR": 4,
            "JUIN": 6, "JUIL": 7, "AOÛT": 8, "SEPT": 9, "FÉV": 2
        }

        if isinstance(date_str, str) and date_str != "":
            d_m = date_str.split()
            try:
                d = int(d_m[0])
                m = date_dict[d_m[1]]
                # Rollover logic
                year = statement_year - 1 if (statement_month == 1 and m == 12) else statement_year
                return datetime(year, m, d)
            except Exception:
                return None
        return None

    def set_col_to_numeric(self, df, col_list):
        for col in col_list:
            if col not in df.columns: continue
            df[col] = df[col].apply(lambda x: x.replace(' ', '') if isinstance(x, str) else x)
            df[col] = df[col].apply(lambda x: x.replace(',', '') if isinstance(x, str) else x)
            try:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            except Exception:
                pass

    def process_compte_operations_courrantes(self, df, statement_year, statement_month):
        df_copy = df.copy()
        # Normalize columns for identification
        df_copy.columns = [str(c).strip() for c in df_copy.columns]
        
        try:
            Unnamed_col_index = df_copy.columns.to_list().index('Unnamed: 0')
            if Unnamed_col_index == 3:
                df_copy = df_copy.drop(['Unnamed: 0', 'Description'], axis=1)
                df_copy = df_copy.rename(columns={'Code': 'Description'})
                if 'Date' in df_copy.columns:
                    df_copy = df_copy.loc[~((df_copy['Description'] == 'Solde reporté') | df_copy['Date'].isna())]
                df_copy["Code"] = df_copy["Description"].str.split().str[0]
                df_copy['Code'] = df_copy['Code'].replace('IVMWVirement', 'IVMW')
                df_copy['Description'] = df_copy.apply(
                    lambda row: row['Description'].replace(row['Code'], '') if pd.notna(row['Description']) and pd.notna(
                        row['Code']) else None, axis=1)
            elif Unnamed_col_index == 2:
                df_copy = df_copy.drop('Description', axis=1)
                df_copy = df_copy.rename(columns={'Unnamed: 0': 'Description'})
                if 'Date' in df_copy.columns:
                    df_copy = df_copy.loc[~((df_copy['Description'] == 'Solde reporté') | df_copy['Date'].isna())]
        except (ValueError, KeyError):
            pass

        self.set_col_to_numeric(df_copy, ['Retrait', 'Dépôt', 'Solde'])
        if 'Date' in df_copy.columns:
            df_copy["Date"] = df_copy["Date"].apply(lambda d: self.to_date(d, statement_year, statement_month))
        
        df_copy = df_copy.rename(columns={"Solde": "SOLDE", "Date": "DATE", "Retrait": "DEBIT", "Dépôt": "CREDIT",
                                "Description": "DESCRIPTION"})
        return df_copy

    def process_compte_celi(self, df, statement_year, statement_month):
        df_copy = df.copy()
        column_names = df_copy.columns.to_list()
        nombre_de_colone = len(column_names)
        new_row = pd.DataFrame([column_names], columns=column_names)
        df_copy = pd.concat([new_row, df_copy], ignore_index=True)

        if nombre_de_colone == 5:
            df_copy.columns = ['Date', 'Code', 'Description', 'Transaction', 'Solde']
            df_copy["Solde"] = pd.to_numeric(df_copy["Solde"].astype(str).str.replace(" ", ""), errors='coerce')
            df_copy["Solde"] = df_copy["Solde"].fillna(0)
            difference = df_copy["Solde"].diff()
            df_copy = df_copy.replace(to_replace=r'.*Unnamed.*', value='', regex=True)

            liste_de_depot, liste_de_retrait = [], []
            for k, v in df_copy.iterrows():
                if v["Description"] != "Solde reporté" and v["Description"] != "Fermeture de compte":
                    if difference[k] > 0:
                        liste_de_depot.append(v['Transaction'])
                        liste_de_retrait.append(0)
                    elif difference[k] < 0:
                        liste_de_depot.append(0)
                        liste_de_retrait.append(v['Transaction'])
                    else:
                        liste_de_depot.append(0); liste_de_retrait.append(0)
                else:
                    liste_de_depot.append(0); liste_de_retrait.append(0)

            df_copy['Retrait'], df_copy['Dépôt'] = liste_de_retrait, liste_de_depot
            df_copy = df_copy.drop('Transaction', axis=1)
        elif nombre_de_colone == 6:
            df_copy.columns = ['Date', 'Code', 'Description', 'Retrait', 'Dépôt', 'Solde']

        self.set_col_to_numeric(df_copy, ['Retrait', 'Dépôt'])
        if 'Date' in df_copy.columns:
            df_copy["Date"] = df_copy["Date"].apply(lambda d: self.to_date(d, statement_year, statement_month))
        
        if 'Description' in df_copy.columns and 'Date' in df_copy.columns:
            df_copy = df_copy.loc[~((df_copy['Description'] == 'Solde reporté') | df_copy['Date'].isna())]
            
        df_copy = df_copy.rename(columns={"Solde": "SOLDE", "Date": "DATE", "Retrait": "DEBIT", "Dépôt": "CREDIT",
                                "Description": "DESCRIPTION"})
        return df_copy

    def process_legacy(self, df, statement_year, statement_month) -> pd.DataFrame:
        cols = [str(c).upper() for c in df.columns]
        if 'RETRAIT' in cols and 'DÉPÔT' in cols:
            df_legacy = self.process_compte_operations_courrantes(df, statement_year, statement_month)
        else:
            df_legacy = self.process_compte_celi(df, statement_year, statement_month)

        if df_legacy.empty:
            return pd.DataFrame(columns=['date', 'description', 'amount', 'account_identifier'])

        df_legacy['amount'] = df_legacy['CREDIT'].fillna(0) - df_legacy['DEBIT'].fillna(0)
        df_legacy.rename(columns={'DATE': 'date', 'DESCRIPTION': 'description'}, inplace=True)
        df_legacy['account_identifier'] = df_legacy['description'].apply(
            lambda x: 'SAVINGS' if any(k in str(x).upper() for k in ['CELI', 'EPARGNE']) else 'CHECKING'
        )
        return df_legacy[['date', 'description', 'amount', 'account_identifier']]

    def process_dynamic(self, df, statement_year, statement_month) -> pd.DataFrame:
        df.columns = [str(c).upper() for c in df.columns]
        date_col = next((c for c in df.columns if 'DATE' in c), None)
        desc_col = next((c for c in df.columns if 'DESCRIPTION' in c), None)
        debit_col = next((c for c in df.columns if 'RETRAIT' in c), None)
        credit_col = next((c for c in df.columns if 'DÉPÔT' in c or 'DEPOT' in c), None)
        frais_col = next((c for c in df.columns if 'FRAIS' in c), None)

        if not date_col or not desc_col: return pd.DataFrame()

        df_dyn = df.copy()
        df_dyn['date'] = df_dyn[date_col].apply(lambda d: self.to_date(d, statement_year, statement_month))
        df_dyn = df_dyn.dropna(subset=['date'])
        
        for col in [debit_col, credit_col, frais_col]:
            if col:
                df_dyn[col] = pd.to_numeric(df_dyn[col].astype(str).str.replace('[ ,$]', '', regex=True), errors='coerce').fillna(0)

        debit_val = df_dyn[debit_col] if debit_col else 0
        credit_val = df_dyn[credit_col] if credit_col else 0
        frais_val = df_dyn[frais_col] if frais_col else 0
        
        df_dyn['amount'] = credit_val - debit_val - frais_val
        df_dyn['description'] = df_dyn[desc_col]
        df_dyn['account_identifier'] = df_dyn['description'].apply(
            lambda x: 'SAVINGS' if any(k in str(x).upper() for k in ['CELI', 'EPARGNE']) else 'CHECKING'
        )
        return df_dyn[['date', 'description', 'amount', 'account_identifier']]

    def process_dataframe(self, df: pd.DataFrame, statement_year: int, statement_month: int) -> tuple[pd.DataFrame, bool]:
        import logging
        logger = logging.getLogger(__name__)

        try:
            df_legacy = self.process_legacy(df.copy(), statement_year, statement_month)
        except Exception as e:
            logger.error(f"Legacy extraction failed: {e}")
            df_legacy = pd.DataFrame(columns=['date', 'description', 'amount', 'account_identifier'])

        try:
            df_dynamic = self.process_dynamic(df.copy(), statement_year, statement_month)
        except Exception as e:
            logger.error(f"Dynamic extraction failed: {e}")
            df_dynamic = pd.DataFrame()

        legacy_count, dynamic_count = len(df_legacy), len(df_dynamic)
        legacy_sum = df_legacy['amount'].sum() if not df_legacy.empty else 0
        dynamic_sum = df_dynamic['amount'].sum() if not df_dynamic.empty else 0

        mismatch = False
        if legacy_count != dynamic_count or abs(legacy_sum - dynamic_sum) > 0.01:
            logger.warning(f"SHADOW MODE MISMATCH: Legacy found {legacy_count} rows (Sum: {legacy_sum}), Dynamic found {dynamic_count} rows (Sum: {dynamic_sum}).")
            mismatch = True
        else:
            logger.info("SHADOW MODE MATCH: Both extractors yielded identical high-level results.")

        return df_legacy, mismatch
