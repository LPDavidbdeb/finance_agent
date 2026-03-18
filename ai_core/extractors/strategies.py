import pandas as pd
from .base import BasePDFExtractor


class VisaDesjardinsExtractor(BasePDFExtractor):
    def tabula_parameters(self) -> dict:
        return {'pages': 'all', 'stream': True}

    def process_dataframe(self, df: pd.DataFrame, extract_year: int) -> pd.DataFrame:
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
            return pd.DataFrame(columns=['date', 'description', 'amount', 'account_identifier'])

        df_clean = df.copy()
        date_pattern = r'^(\d{2})\s(\d{2})'
        desc_col = next((col for col in df_clean.columns if 'DESCRIPTION' in col), 'DESCRIPTION')
        amount_col = next((col for col in df_clean.columns if 'MONTANT' in col), 'MONTANT')

        extracted_dates = df_clean[desc_col].astype(str).str.extract(date_pattern)
        valid_rows = extracted_dates[0].notna() & extracted_dates[1].notna()
        df_clean = df_clean[valid_rows].copy()

        df_clean['date'] = pd.to_datetime(
            dict(year=extract_year, month=extracted_dates[1][valid_rows].astype(int),
                 day=extracted_dates[0][valid_rows].astype(int)),
            errors='coerce'
        )

        df_clean['description'] = df_clean[desc_col].astype(str).str[12:].str.strip()
        df_clean['amount'] = df_clean[amount_col].astype(str).str.replace('%', '', regex=False).str.replace(' ', '',
                                                                                                            regex=False).str.replace(
            ',', '.', regex=False).str.replace('CR', '', regex=False)
        df_clean['amount'] = pd.to_numeric(df_clean['amount'], errors='coerce')
        df_clean['account_identifier'] = 'CREDIT_CARD'

        return df_clean[['date', 'description', 'amount', 'account_identifier']].dropna(subset=['date', 'amount'])


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

    def process_dataframe(self, df: pd.DataFrame, extract_year: int) -> pd.DataFrame:
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
                return temp_df[['date', 'description', 'amount', 'account_identifier']].dropna(subset=['date'])
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
                return stacked_df[['date', 'description', 'amount', 'account_identifier']].dropna(subset=['date'])

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
            return df[['date', 'description', 'amount', 'account_identifier']].dropna(subset=['date'])

        return pd.DataFrame(columns=['date', 'description', 'amount', 'account_identifier'])