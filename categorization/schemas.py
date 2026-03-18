from ninja import Schema
from typing import Optional

class RuleCreateAndApplyIn(Schema):
    search_text: str
    merchant_name: str
    target_account_id: int
    institution_id: Optional[int] = None
