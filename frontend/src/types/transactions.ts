export interface StagedTransactionView {
  id: number;
  bank_date: string;
  raw_description: string;
  clean_description?: string;
  merchant_name?: string;
  amount: number;
  status: string;
  statement_import_id: number;
  predicted_account_id?: number;
  predicted_account_name?: string;
  reconciled_account_name?: string;
  journal_entry_id?: number;
  financial_product_id?: number;
  institution_id?: number;
}

