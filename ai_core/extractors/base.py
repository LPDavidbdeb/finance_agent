import pandas as pd
import tabula
from abc import ABC, abstractmethod


class BasePDFExtractor(ABC):
    def extract(self, pdf_path: str, statement_year: int, statement_month: int) -> pd.DataFrame:
        try:
            dfs = tabula.read_pdf(pdf_path, **self.tabula_parameters())
            if not dfs:
                return pd.DataFrame(columns=['date', 'description', 'amount', 'account_identifier'])

            processed_dfs = []
            for df in dfs:
                clean_df = self.process_dataframe(df, statement_year, statement_month)
                if not clean_df.empty:
                    processed_dfs.append(clean_df)

            if processed_dfs:
                combined_df = pd.concat(processed_dfs, ignore_index=True)
                if all(col in combined_df.columns for col in ['date', 'description', 'amount', 'account_identifier']):
                    return combined_df[['date', 'description', 'amount', 'account_identifier']]

            return pd.DataFrame(columns=['date', 'description', 'amount', 'account_identifier'])
        except Exception as e:
            print(f"Extraction error: {e}")
            return pd.DataFrame(columns=['date', 'description', 'amount', 'account_identifier'])

    @abstractmethod
    def process_dataframe(self, df: pd.DataFrame, statement_year: int, statement_month: int) -> pd.DataFrame:
        pass

    def tabula_parameters(self) -> dict:
        return {'pages': 'all', 'stream': False}
