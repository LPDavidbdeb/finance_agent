from ninja import Schema
from typing import Optional, List

class RuleCreateAndApplyIn(Schema):
    search_text: str
    merchant_name: str
    target_account_id: Optional[int] = None
    is_unique_provider: bool = True
    institution_id: Optional[int] = None

class MerchantOut(Schema):
    id: int
    name: str
    is_unique_provider: bool
    default_account_id: Optional[int] = None
    default_account_name: Optional[str] = None

class MerchantUpdateIn(Schema):
    name: Optional[str] = None
    default_account_id: Optional[int] = None
    is_unique_provider: Optional[bool] = None
    update_history: bool = False

class MappingRuleOut(Schema):
    id: int
    search_text: str
    institution_name: Optional[str] = None

    @staticmethod
    def resolve_institution_name(obj):
        return obj.institution.name if obj.institution else "All Institutions"

class MerchantDetailOut(Schema):
    id: int
    name: str
    is_unique_provider: bool
    default_account_id: Optional[int] = None
    default_account_name: Optional[str] = None
    mapping_rules: List[MappingRuleOut]

    @staticmethod
    def resolve_default_account_name(obj):
        return obj.default_account.name if obj.default_account else None

    @staticmethod
    def resolve_default_account_id(obj):
        return obj.default_account_id

class MerchantMergeIn(Schema):
    target_id: int
    source_ids: List[int]
