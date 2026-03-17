from ninja import Schema
from typing import Optional

class FinancialProductIn(Schema):
    institution_id: int
    product_type: str
    product_name: str
    owner_id: Optional[int] = None

class InstitutionIn(Schema):
    name: str

class InstitutionOut(Schema):
    id: int
    name: str

class FinancialProductOut(Schema):
    id: int
    product_type: str
    account_name: str
    owner_id: Optional[int] = None

    @staticmethod
    def resolve_account_name(obj):
        return obj.account.name