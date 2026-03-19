from ninja import Schema
from typing import Optional

class RuleCreateAndApplyIn(Schema):
    search_text: str
    merchant_name: str
    target_account_id: int
    institution_id: Optional[int] = None

class MerchantOut(Schema):
    id: int
    name: str
    default_account_id: Optional[int] = None
    default_account_name: Optional[str] = None

class MerchantUpdateIn(Schema):
    default_account_id: int
