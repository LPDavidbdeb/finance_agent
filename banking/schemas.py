from ninja import Schema
from typing import Optional

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