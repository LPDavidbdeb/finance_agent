export interface AccountChildAccount {
  id: number;
  name: string;
  account_type: string;
  balance: number;
}

export interface AccountMerchantSummary {
  id: number;
  name: string;
  balance: number;
}

export interface MonthlyCategoryBreakdown {
  child_id: number;
  child_name: string;
  amount: number;
}

export interface MonthlyBreakdown {
  month: string;
  total: number;
  by_child: MonthlyCategoryBreakdown[];
}

export interface CFAInsights {
  amount_current: number;
  amount_previous: number;
  yoy_growth?: number;
  share_of_parent: number;
  share_of_total_inflow: number;
  volatility_score: number;
  concentration_top_1: number;
  drift_spread?: number;
  optimization_headroom?: number;
  burn_coverage_days?: number;
  health_tag: string;
  red_flag?: { title: string; detail: string };
  green_flag?: { title: string; detail: string };
  strategic_action?: { action: string; owner: string; time_horizon: string };
}

export interface YearlyTrend {
  year: number;
  total: number;
  realized_total: number;
  estimated_total: number;
  monthly_avg: number;
  pct_of_income: number;
  breakdown?: Record<string, number>;
}

export interface AccountDetailRecord {
  id: number;
  name: string;
  account_type: string;
  parent_id?: number;
  children: AccountChildAccount[];
  direct_merchants: AccountMerchantSummary[];
  insights: CFAInsights;
  monthly_breakdown: MonthlyBreakdown[];
  all_historical_months?: MonthlyBreakdown[];
  historical_trends: YearlyTrend[];
  avg_yearly_total: number;
  avg_monthly_avg: number;
}

export interface AccountTransactionRecord {
  journal_entry_id: number;
  date: string;
  description: string;
  amount: number;
  status: string;
  source_account: string;
  routed_to: string;
  routed_to_id: number;
  institution_id?: number | null;
  statement_id?: number | null;
}
