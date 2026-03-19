from ninja import Schema
from typing import List, Optional

class AccountChildOut(Schema):
    id: int
    name: str
    account_type: str

class AccountMerchantOut(Schema):
    id: int
    name: str

class AccountDetailOut(Schema):
    id: int
    name: str
    account_type: str
    parent_id: Optional[int] = None
    children: List[AccountChildOut]
    merchants: List[AccountMerchantOut]

    @staticmethod
    def resolve_children(obj):
        return obj.get_children()

    @staticmethod
    def resolve_merchants(obj):
        return obj.merchants.all()

class DimensionLineItemOut(Schema):
    id: Optional[int] = None
    name: str
    balance: float

class DimensionBreakdownOut(Schema):
    dimension_name: str
    total_amount: float
    line_items: List[DimensionLineItemOut]
