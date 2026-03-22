from ninja import Schema
from typing import List, Optional

class AccountChildOut(Schema):
    id: int
    name: str
    account_type: str
    balance: float = 0.0

class AccountOut(Schema):
    id: int
    name: str
    account_type: str
    parent_id: Optional[int] = None
    children: List['AccountOut'] = []

class AccountCreateIn(Schema):
    name: str
    parent_id: int
    account_type: Optional[str] = None

AccountOut.update_forward_refs()

class AccountMerchantOut(Schema):
    id: int
    name: str
    balance: float = 0.0

class MonthlyCategoryBreakdownOut(Schema):
    child_id: int
    child_name: str
    amount: float

class MonthlyBreakdownOut(Schema):
    month: str # YYYY-MM
    total: float
    by_child: List[MonthlyCategoryBreakdownOut]

class CFAInsightsOut(Schema):
    # Universal context
    amount_current: float
    amount_previous: float
    yoy_growth: Optional[float] = None
    share_of_parent: float
    share_of_total_inflow: float
    volatility_score: float # Std Dev of last 12 months
    concentration_top_1: float # % of branch held by top merchant/child
    
    # Specific Lenses (Conditional)
    drift_spread: Optional[float] = None # Growth of this node - Growth of Revenue Root
    optimization_headroom: Optional[float] = None # 5% of top vendor
    burn_coverage_days: Optional[float] = None # Total Assets / (Branch Amount / 365)
    
    # Flags
    health_tag: str # 'sturdy' | 'volatile' | 'drifting' | 'concentrated'
    red_flag: Optional[dict] = None
    green_flag: Optional[dict] = None
    strategic_action: Optional[dict] = None

class YearlyTrendOut(Schema):
    year: int
    total: float
    monthly_avg: float
    breakdown: dict = {} # Map of child_name -> amount

class AccountDetailOut(Schema):
    id: int
    name: str
    account_type: str
    parent_id: Optional[int] = None
    children: List[AccountChildOut]
    direct_merchants: List[AccountMerchantOut]
    insights: CFAInsightsOut
    historical_trends: List[YearlyTrendOut] = []
    monthly_breakdown: List[MonthlyBreakdownOut] = []
    avg_yearly_total: float = 0.0
    avg_monthly_avg: float = 0.0

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
