from ninja import Schema
from typing import Optional, List

class RuleCreateAndApplyIn(Schema):
    search_text: str
    merchant_name: str
    target_account_id: Optional[int] = None
    is_unique_provider: bool = True
    institution_id: Optional[int] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    linked_schedule_id: Optional[int] = None


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
    linked_schedule_id: Optional[int] = None   # set to link; omit to leave unchanged
    clear_linked_schedule: bool = False         # set True to unlink

class MappingRuleOut(Schema):
    id: int
    search_text: str
    institution_name: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None

    @staticmethod
    def resolve_institution_name(obj):
        return obj.institution.name if obj.institution else "All Institutions"

class MerchantDetailOut(Schema):
    id: int
    name: str
    is_unique_provider: bool
    default_account_id: Optional[int] = None
    default_account_name: Optional[str] = None
    linked_schedule_id: Optional[int] = None
    linked_schedule_name: Optional[str] = None
    mapping_rules: List[MappingRuleOut]

    @staticmethod
    def resolve_default_account_name(obj):
        return obj.default_account.name if obj.default_account else None

    @staticmethod
    def resolve_default_account_id(obj):
        return obj.default_account_id

    @staticmethod
    def resolve_linked_schedule_id(obj):
        return obj.linked_schedule_id

    @staticmethod
    def resolve_linked_schedule_name(obj):
        return obj.linked_schedule.name if obj.linked_schedule else None

class MerchantMergeIn(Schema):
    target_id: int
    source_ids: List[int]

class RuleYearlyStatOut(Schema):
    year: int
    total: float
    count: int

class RuleStatsOut(Schema):
    yearly: List[RuleYearlyStatOut]

class MerchantStatsOut(Schema):
    total_amount: float
    historical_monthly_avg: float
    current_year_monthly_avg: float
    daily_activity: List[dict]
