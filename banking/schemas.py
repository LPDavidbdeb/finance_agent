from ninja import Schema
from typing import Optional
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
    amount: Decimal
    status: str
    statement_import_id: int
    predicted_account_id: Optional[int] = None
    predicted_account_name: Optional[str] = None

    @staticmethod
    def resolve_predicted_account_id(obj):
        return obj.predicted_account.id if obj.predicted_account else None

    @staticmethod
    def resolve_predicted_account_name(obj):
        return obj.predicted_account.name if obj.predicted_account else None

class TransactionApproveIn(Schema):
    target_account_id: int
