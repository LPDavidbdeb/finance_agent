from ninja import Schema
from typing import List, Optional

class AccountChildOut(Schema):
    id: int
    name: str
    account_type: str

class AccountMerchantOut(Schema):
    id: int
    name: str
    balance: float = 0.0

class AccountDetailOut(Schema):
    id: int
    name: str
    account_type: str
    parent_id: Optional[int] = None
    children: List[AccountChildOut]
    merchants: List[AccountMerchantOut]

class DimensionLineItemOut(Schema):
    id: Optional[int] = None
    name: str
    balance: float
    sub_items: List[dict] = []

class MerchantItemOut(Schema):
    id: int
    name: str
    balance: float

class DimensionBreakdownOut(Schema):
    dimension_name: str
    total_amount: float
    line_items: List[DimensionLineItemOut]
    merchant_items: List[MerchantItemOut] = []
