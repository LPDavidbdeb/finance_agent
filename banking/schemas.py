from ninja import Schema
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal

class FinancialProductIn(Schema):
    institution_id: int
    product_type: str
    product_name: str
    owner_id: int
    account_number: Optional[str] = None

class InstitutionIn(Schema):
    name: str

class InstitutionOut(Schema):
    id: int
    name: str

class FinancialProductOut(Schema):
    id: int
    institution_id: int
    product_type: str
    account_number: Optional[str] = None
    owner_id: Optional[int] = None
    account_name: str
    institution_name: str
    accounting_post: str

    @staticmethod
    def resolve_account_name(obj):
        return obj.account.name
        
    @staticmethod
    def resolve_institution_name(obj):
        return obj.institution.name

    @staticmethod
    def resolve_accounting_post(obj):
        # Traverse up one level to get the accounting category (e.g., "Bank Accounts", "Investments")
        # because the product's immediate account is the leaf node.
        if obj.account and obj.account.parent:
            return obj.account.parent.name
        return "Uncategorized"

class StatementUploadOut(Schema):
    id: int
    file_url: Optional[str] = None
    status: str

    @staticmethod
    def resolve_file_url(obj):
        return obj.file.url if obj.file else None


class StatementImportOut(Schema):
    id: int
    institution_id: Optional[int] = None
    financial_product_id: Optional[int] = None
    upload_date: datetime
    document_date: Optional[date] = None
    file_name: str
    file_url: Optional[str] = None
    processed_by_ai: bool
    processed_by_python: bool
    status: str

    @staticmethod
    def resolve_file_name(obj):
        if not obj.file:
            return ""
        return obj.file.name.split("/")[-1]

    @staticmethod
    def resolve_file_url(obj):
        return obj.file.url if obj.file else None

class StagedTransactionOut(Schema):
    id: int
    bank_date: date
    raw_description: str
    clean_description: Optional[str] = None
    merchant_name: Optional[str] = None
    amount: Decimal
    status: str
    statement_import_id: int
    predicted_account_id: Optional[int] = None
    predicted_account_name: Optional[str] = None
    reconciled_account_name: Optional[str] = None
    journal_entry_id: Optional[int] = None
    financial_product_id: Optional[int] = None
    institution_id: Optional[int] = None

    @staticmethod
    def resolve_clean_description(obj):
        return obj.merchant.name if obj.merchant else obj.raw_description

    @staticmethod
    def resolve_merchant_name(obj):
        return obj.merchant.name if obj.merchant else None

    @staticmethod
    def resolve_predicted_account_id(obj):
        return obj.predicted_account.id if obj.predicted_account else None

    @staticmethod
    def resolve_predicted_account_name(obj):
        return obj.predicted_account.name if obj.predicted_account else None

    @staticmethod
    def resolve_reconciled_account_name(obj):
        if not obj.journal_entry:
            return None
        # The category is the account that does NOT have a linked FinancialProduct
        # (The other side of the double-entry is the bank account)
        for line in obj.journal_entry.lines.all():
            # Use hasattr check for OneToOne reverse relationship
            if not hasattr(line.account, 'financial_product'):
                return line.account.name
        return None

    @staticmethod
    def resolve_journal_entry_id(obj):
        return obj.journal_entry_id

    @staticmethod
    def resolve_financial_product_id(obj):
        if obj.financial_product_id:
            return obj.financial_product_id
        if obj.statement_import and obj.statement_import.financial_product_id:
            return obj.statement_import.financial_product_id
        return None

    @staticmethod
    def resolve_institution_id(obj):
        product = obj.financial_product or (obj.statement_import.financial_product if obj.statement_import else None)
        return product.institution_id if product else None

class StatementMonthOut(Schema):
    month: date
    display_name: str
    transaction_count: int

class TransactionApproveIn(Schema):
    target_account_id: int

class StatementCellOut(Schema):
    month: str           # "YYYY-MM"
    statement_id: Optional[int] = None   # None = missing
    status: Optional[str] = None

class TargetCoverageOut(Schema):
    """
    One row in the coverage grid.

    target_type = 'INSTITUTION' → consolidated multi-product upload target
                                   (e.g. Tangerine).  target_id is the
                                   FinancialInstitution.id.
    target_type = 'PRODUCT'     → legacy single-product upload target.
                                   target_id is the FinancialProduct.id.
    """
    target_id: int
    target_name: str     # "Tangerine (Consolidé)"  |  "Desjardins Boni Visa"
    target_type: str     # 'INSTITUTION' | 'PRODUCT'
    months: List['StatementCellOut']

class StatementCoverageOut(Schema):
    all_months: List[str]            # ordered "YYYY-MM" strings — column headers
    targets: List[TargetCoverageOut]
