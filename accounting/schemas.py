from ninja import Schema
from typing import List, Optional
from datetime import date
from decimal import Decimal

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
    realized_total: float = 0.0
    estimated_total: float = 0.0
    monthly_avg: float
    pct_of_income: float = 0.0
    breakdown: dict = {} # Map of child_name -> amount

class DrillDownBannerOut(Schema):
    name: str
    amount: float
    count: int
    category: str

class DrillDownOut(Schema):
    dimension_name: str
    period: str
    category_breakdown: List['DimensionLineItemOut']
    banners: List[DrillDownBannerOut]

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
    average_monthly_balance: float = 0.0
    sub_items: List[dict] = []

DrillDownOut.update_forward_refs()

class MerchantItemOut(Schema):
    id: int
    name: str
    balance: float

class DimensionBreakdownOut(Schema):
    dimension_name: str
    total_amount: float
    line_items: List[DimensionLineItemOut]
    merchant_items: List[MerchantItemOut] = []

class BannerTransactionOut(Schema):
    journal_entry_id: int
    date: date
    amount: float
    source_account: str
    routed_to: str
    routed_to_id: int
    statement_id: Optional[int] = None
    raw_description: str
    institution_id: Optional[int] = None

class AccountTransactionOut(Schema):
    journal_entry_id: int
    date: date
    description: str
    amount: float
    source_account: str
    routed_to: str
    routed_to_id: int
    institution_id: Optional[int] = None
    statement_id: Optional[int] = None

class RerouteIn(Schema):
    new_account_id: Optional[int] = None
    merchant_id: Optional[int] = None

class FlatAccountOut(Schema):
    id: int
    name: str
    account_type: str
    depth: int

class AnnualYearDataOut(Schema):
    year: int
    revenue: float
    expenses: float
    net_income: float
    assets: float
    liabilities: float
    net_worth: float

class AnnualHistoryOut(Schema):
    years: List[AnnualYearDataOut]


class MonthlyExpensePointOut(Schema):
    month: str
    amount: float


class MonthlyExpenseCategoryOut(Schema):
    category_id: int
    category_name: str
    all_time_average: float
    current_month_amount: float
    delta_vs_average: float
    delta_vs_average_pct: Optional[float] = None
    series: List[MonthlyExpensePointOut]


class MerchantSeriesOut(Schema):
    id: int
    name: str
    series: List[MonthlyExpensePointOut]


class MonthlyExpenseTransactionOut(Schema):
    journal_entry_id: int
    date: date
    description: str
    amount: float
    category_id: int
    category_name: str
    merchant_name: Optional[str] = None
    statement_id: Optional[int] = None
    staged_transaction_id: Optional[int] = None


class MonthlySummaryPointOut(Schema):
    month: str
    revenue: float
    expenses: float
    savings: float


class MonthlyExpenseReportOut(Schema):
    latest_month: Optional[str] = None
    latest_revenue: float = 0.0
    latest_expenses: float = 0.0
    latest_savings: float = 0.0
    avg_revenue: float = 0.0
    avg_expenses: float = 0.0
    avg_savings: float = 0.0
    totals_series: List[MonthlyExpensePointOut]
    summary_series: List[MonthlySummaryPointOut] = []
    categories: List[MonthlyExpenseCategoryOut]
    revenue_categories: List[MonthlyExpenseCategoryOut] = []
    merchants: List["MerchantSeriesOut"] = []
    top_transactions: List[MonthlyExpenseTransactionOut] = []


class InsightFactOut(Schema):
    id: int
    category_id: int
    insight_score: float
    materiality_pct: float
    process_type: str
    expert_summary: str
    projected_value: float | None = None
    projected_lower_bound: Decimal | None = None
    projected_upper_bound: Decimal | None = None
    benchmark_slope: Decimal | None = None
    benchmark_classification: Optional[str] = None

