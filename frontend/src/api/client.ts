// Centralized API configuration from environment variables
export const API_URL = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8001/api`;
export const BASE_URL = import.meta.env.VITE_BASE_URL || `http://${window.location.hostname}:8001`;

// Helper to get the auth header
function getAuthHeader() {
  const token = localStorage.getItem('access_token');
  return {
    "Content-Type": "application/json",
    "Authorization": token ? `Bearer ${token}` : ""
  };
}

// --- Accounting API ---

export async function fetchSpendingEvolution(startDate: string, endDate: string, interval: string = 'monthly') {
  const res = await fetch(`${API_URL}/accounting/spending-evolution?start_date=${startDate}&end_date=${endDate}&interval=${interval}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch spending evolution");
  return res.json();
}

export async function fetchDimensionEvolution(dimension: string, startDate: string, endDate: string, interval: string = 'monthly') {
  const res = await fetch(`${API_URL}/accounting/dimension-evolution?dimension=${dimension}&start_date=${startDate}&end_date=${endDate}&interval=${interval}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch dimension evolution");
  return res.json();
}


export async function fetchSpendingByCategory(startDate: string, endDate: string) {
  const res = await fetch(`${API_URL}/accounting/spending-by-category?start_date=${startDate}&end_date=${endDate}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch spending by category");
  return res.json();
}

export interface MonthlyExpensePoint {
  month: string;
  amount: number;
}

export interface MerchantSeriesPoint {
  month: string;
  amount: number;
}

export interface MerchantSeries {
  id: number;
  name: string;
  series: MerchantSeriesPoint[];
}

export interface MonthlyExpenseTransaction {
  journal_entry_id: number;
  date: string;
  description: string;
  amount: number;
  category_id: number;
  category_name: string;
  merchant_name?: string | null;
  statement_id?: number | null;
  staged_transaction_id?: number | null;
}

export interface MonthlyExpenseCategory {
  category_id: number;
  category_name: string;
  all_time_average: number;
  current_month_amount: number;
  delta_vs_average: number;
  delta_vs_average_pct: number | null;
  series: MonthlyExpensePoint[];
}

export interface MonthlySummaryPoint {
  month: string;
  revenue: number;
  expenses: number;
  savings: number;
}

export interface MonthlyExpenseReport {
  latest_month: string | null;
  latest_revenue: number;
  latest_expenses: number;
  latest_savings: number;
  avg_revenue: number;
  avg_expenses: number;
  avg_savings: number;
  totals_series: MonthlyExpensePoint[];
  summary_series: MonthlySummaryPoint[];
  categories: MonthlyExpenseCategory[];
  revenue_categories: MonthlyExpenseCategory[];
  merchants?: MerchantSeries[];
  top_transactions?: MonthlyExpenseTransaction[];
}

export async function fetchMonthlyExpenseOverview(selectedMonth?: string | null): Promise<MonthlyExpenseReport> {
  const query = selectedMonth ? `?selected_month=${encodeURIComponent(selectedMonth)}` : '';
  const res = await fetch(`${API_URL}/accounting/reports/expenses/monthly-overview${query}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch monthly expense overview");
  return res.json();
}

export async function fetchMonthlyExpenseOverviewPdf(selectedMonth?: string | null): Promise<Blob> {
  const query = selectedMonth ? `?selected_month=${encodeURIComponent(selectedMonth)}` : '';
  const res = await fetch(`${API_URL}/accounting/reports/expenses/monthly-overview/pdf${query}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch monthly expense report PDF");
  return res.blob();
}

export async function fetchAvailableYears() {
  const res = await fetch(`${API_URL}/accounting/available-years`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch available years");
  return res.json();
}

export async function fetchAnnualStatements(year: number) {
  const res = await fetch(`${API_URL}/accounting/annual-statements?year=${year}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch annual statements");
  return res.json();
}

export interface AnnualYearData {
  year: number;
  revenue: number;
  expenses: number;
  net_income: number;
  assets: number;
  liabilities: number;
  net_worth: number;
}

export async function fetchAnnualStatementsHistory(): Promise<{ years: AnnualYearData[] }> {
  const res = await fetch(`${API_URL}/accounting/annual-statements/history`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch annual history");
  return res.json();
}

export async function fetchDimensionDetail(slug: string, year: number) {
  const res = await fetch(`${API_URL}/accounting/reports/dimension/${slug}?year=${year}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch dimension breakdown");
  return res.json();
}

export async function fetchDrillDown(slug: string, period: string) {
  const res = await fetch(`${API_URL}/accounting/reports/dimension/${slug}/drill-down?period=${period}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch drill-down data");
  return res.json();
}

export async function fetchAccountTransactions(accountId: number, year?: number) {
  const url = `${API_URL}/accounting/accounts/${accountId}/journal-entries${year ? `?year=${year}` : ''}`;
  const res = await fetch(url, { headers: getAuthHeader() });
  if (!res.ok) throw new Error("Failed to fetch account transactions");
  return res.json();
}

export async function fetchAccountsFlat() {
  const res = await fetch(`${API_URL}/accounting/accounts-flat`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch accounts");
  return res.json();
}

export async function rerouteJournalEntry(entryId: number, newAccountId?: number, merchantId?: number) {
  const res = await fetch(`${API_URL}/accounting/journal-entries/${entryId}/reroute`, {
    method: "PATCH",
    headers: getAuthHeader(),
    body: JSON.stringify({ 
      new_account_id: newAccountId,
      merchant_id: merchantId 
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to reroute transaction");
  }
  return res.json();
}

export async function fetchBannerTransactions(slug: string, period: string, banner: string) {
  const res = await fetch(
    `${API_URL}/accounting/reports/dimension/${slug}/banner-transactions?period=${period}&banner=${encodeURIComponent(banner)}`,
    { headers: getAuthHeader() }
  );
  if (!res.ok) throw new Error("Failed to fetch banner transactions");
  return res.json();
}

export async function runMaintenanceCommand(command: string, args: string[] = []) {
  const res = await fetch(`${API_URL}/maintenance/run-command`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ command, args }),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Maintenance command failed");
  }
  return res.json();
}

export async function fetchAccountDetail(id: number, year?: number) {
  const url = `${API_URL}/accounting/accounts/${id}${year ? `?year=${year}` : ''}`;
  const res = await fetch(url, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch account details");
  }
  return res.json();
}

export async function fetchAccountTree() {
  const res = await fetch(`${API_URL}/accounts/tree`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch account tree");
  return res.json();
}

export async function createAccount(data: { name: string; parent_id: number }) {
  const res = await fetch(`${API_URL}/accounting/accounts`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to create account");
  }
  return res.json();
}

export async function deleteAccount(id: number) {
  const res = await fetch(`${API_URL}/accounting/accounts/${id}`, {
    method: "DELETE",
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to delete account");
  }
  return res;
}

export async function moveAccount(accountId: number, targetParentId: number) {
  const res = await fetch(`${API_URL}/accounts/${accountId}/move`, {
    method: "PATCH",
    headers: getAuthHeader(),
    body: JSON.stringify({ target_parent_id: targetParentId }),
  });
  if (!res.ok) throw new Error("Failed to move account");
  return res.json();
}

export async function registerHousehold(data: any) {
  const res = await fetch(`${API_URL}/users/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.message || "Registration failed");
  }
  return res.json();
}

export async function loginUser(credentials: any) {
  const res = await fetch(`${API_URL}/auth/pair`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ 
      email: credentials.email,
      password: credentials.password 
    }),
  });
  
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Invalid email or password");
  }
  
  return res.json();
}

// --- Family Member API ---

export async function fetchFamilyMembers() {
  const res = await fetch(`${API_URL}/users/members`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch family members");
  }
  return res.json();
}

export async function fetchFamilyMember(id: number) {
  const res = await fetch(`${API_URL}/users/members/${id}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch family member");
  }
  return res.json();
}

export async function createFamilyMember(data: any) {
  const res = await fetch(`${API_URL}/users/members`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to create family member");
  }
  return res.json();
}

export async function updateFamilyMember(id: number, data: any) {
  const res = await fetch(`${API_URL}/users/members/${id}`, {
    method: "PUT",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to update family member");
  }
  return res.json();
}

export async function deleteFamilyMember(id: number) {
  const res = await fetch(`${API_URL}/users/members/${id}`, {
    method: "DELETE",
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to delete family member");
  return res.json();
}

// --- Banking API ---

export async function fetchInstitutions() {
  const res = await fetch(`${API_URL}/banking/institutions`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch institutions");
  }
  return res.json();
}

export async function createInstitution(data: any) {
  const res = await fetch(`${API_URL}/banking/institutions`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to create institution");
  }
  return res.json();
}

export async function updateInstitution(id: number, data: any) {
  const res = await fetch(`${API_URL}/banking/institutions/${id}`, {
    method: "PUT",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to update institution");
  }
  return res.json();
}

export async function deleteInstitution(id: number) {
  const res = await fetch(`${API_URL}/banking/institutions/${id}`, {
    method: "DELETE",
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    // Explicitly catch the 400 protected error from Django
    if (res.status === 400) {
      throw new Error(errorData?.detail || "Cannot delete this institution because it is currently linked to one or more financial products.");
    }
    throw new Error("Failed to delete institution");
  }
  return res.json();
}

export async function fetchMemberProducts(memberId: number) {
  const res = await fetch(`${API_URL}/banking/products?owner_id=${memberId}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch member products");
  }
  return res.json();
}

export async function fetchFinancialProduct(id: number) {
  const res = await fetch(`${API_URL}/banking/products/${id}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch financial product");
  }
  return res.json();
}

export async function createFinancialProduct(data: any) {
  const res = await fetch(`${API_URL}/banking/products`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to create financial product");
  }
  return res.json();
}

export async function batchUploadStatements(productId: number, files: File[]) {
  const formData = new FormData();

  for (const file of files) {
    formData.append('files', file);
  }

  const token = localStorage.getItem('access_token');
  const res = await fetch(`${API_URL}/banking/products/${productId}/statements/batch-upload`, {
    method: 'POST',
    headers: { Authorization: token ? `Bearer ${token}` : '' },
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error(errorData?.detail || 'Failed to upload statements');
  }

  return res.json();
}

export async function uploadStatement(productId: number, file: File, documentDate?: string) {
  const token = localStorage.getItem('access_token');
  const formData = new FormData();
  formData.append('file', file);
  if (documentDate) {
    formData.append('document_date', documentDate);
  }

  const res = await fetch(`${API_URL}/banking/products/${productId}/statements/upload`, {
    method: 'POST',
    headers: {
      Authorization: token ? `Bearer ${token}` : '',
    },
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error(errorData?.detail || 'Failed to upload statement');
  }

  return res.json();
}

export async function fetchProductStatements(productId: number) {
  const res = await fetch(`${API_URL}/banking/products/${productId}/statements`, {
    headers: getAuthHeader(),
  });

  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error('Failed to fetch statements');
  }

  return res.json();
}

export async function fetchStatementImport(importId: number) {
  const res = await fetch(`${API_URL}/banking/statements/${importId}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch statement import");
  return res.json();
}

export async function fetchStatementImportTransactions(importId: number) {
  const res = await fetch(`${API_URL}/banking/statements/${importId}/transactions`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch statement transactions");
  return res.json();
}

export async function deleteStatementImport(importId: number) {
  const res = await fetch(`${API_URL}/banking/imports/${importId}`, {
    method: "DELETE",
    headers: getAuthHeader(),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error(errorData?.detail || "Failed to delete statement import");
  }

  return res.json();
}

export async function fetchCeleryStatus() {
  const res = await fetch(`${API_URL}/maintenance/celery-status`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch celery status");
  return res.json();
}

export async function fetchStatementMonths(productId: number) {
  const res = await fetch(`${API_URL}/banking/products/${productId}/statement-months`, {
    headers: getAuthHeader(),
  });

  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error('Failed to fetch statement months');
  }

  return res.json();
}

export async function fetchStatementTransactions(productId: number, year: number, month: number) {
  const res = await fetch(`${API_URL}/banking/products/${productId}/statements/${year}/${month}/transactions`, {
    headers: getAuthHeader(),
  });

  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error('Failed to fetch statement transactions');
  }

  return res.json();
}

// --- Categorization API ---

export async function fetchMerchants() {
  const res = await fetch(`${API_URL}/categorization/merchants`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch merchants");
  }
  return res.json();
}

export async function fetchMerchantDetail(id: number) {
  const res = await fetch(`${API_URL}/categorization/merchants/${id}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch merchant details");
  }
  return res.json();
}

export async function fetchUnmappedStrings(query?: string) {
  const url = `${API_URL}/categorization/unmapped-strings${query ? `?q=${encodeURIComponent(query)}` : ''}`;
  const res = await fetch(url, { headers: getAuthHeader() });
  if (!res.ok) throw new Error("Failed to fetch unmapped strings");
  return res.json();
}

export async function fetchMerchantStats(id: number) {
  const res = await fetch(`${API_URL}/categorization/merchants/${id}/stats`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch merchant stats");
  }
  return res.json();
}

export async function updateMerchant(id: number, data: { name?: string; default_account_id?: number; is_unique_provider?: boolean; update_history?: boolean; linked_schedule_id?: number | null; clear_linked_schedule?: boolean }) {
  const res = await fetch(`${API_URL}/categorization/merchants/${id}`, {
    method: "PATCH",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to update merchant");
  }
  return res.json();
}

export async function mergeMerchants(targetId: number, sourceIds: number[]) {
  const res = await fetch(`${API_URL}/categorization/merchants/merge`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ target_id: targetId, source_ids: sourceIds }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to merge merchants");
  }
  return res.json();
}

export async function updateMerchantAccount(merchantId: number, accountId: number) {
  const res = await fetch(`${API_URL}/categorization/merchants/${merchantId}`, {
    method: "PATCH",
    headers: getAuthHeader(),
    body: JSON.stringify({ default_account_id: accountId }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to update merchant category");
  }
  return res.json();
}

export async function createAndApplyRule(data: {
  search_text: string;
  merchant_name: string;
  target_account_id?: number;
  is_unique_provider?: boolean;
  institution_id?: number;
}) {
  const res = await fetch(`${API_URL}/categorization/create-and-apply`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error(errorData?.detail || "Failed to create and apply rule");
  }

  return res.json();
}

export async function deleteRule(ruleId: number) {
  const res = await fetch(`${API_URL}/categorization/rules/${ruleId}`, {
    method: "DELETE",
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to delete rule");
  }
  return res.json();
}

export async function fetchRuleStats(ruleId: number) {
  const res = await fetch(`${API_URL}/categorization/rules/${ruleId}/stats`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch rule stats");
  return res.json() as Promise<{ yearly: { year: number; total: number; count: number }[] }>;
}

export async function fetchStagedTransactions(productId: number) {
  const res = await fetch(`${API_URL}/banking/products/${productId}/staged-transactions`, {
    headers: getAuthHeader(),
  });

  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error('Failed to fetch staged transactions');
  }

  return res.json();
}

export async function approveTransaction(productId: number, transactionId: number, targetAccountId: number) {
  const res = await fetch(`${API_URL}/banking/products/${productId}/staged-transactions/${transactionId}/approve`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ target_account_id: targetAccountId }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "An unknown error occurred." }));
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error(errorData.detail);
  }

  return res.json();
}

// --- Planning API ---

export interface ScenarioSpec {
  name: string;
  type: 'LOAN_AMORTIZATION' | 'SINKING_FUND';
  principal: number;
  annual_rate: number;
  amortization_years: number;
  payment_frequency: 'MONTHLY' | 'BIWEEKLY' | 'WEEKLY' | 'ANNUALLY';
  start_date: string;
  current_balance?: number;
}

export interface PeriodRow {
  period_number: number;
  payment_date: string;
  payment_amount: number;
  interest_portion: number;
  principal_portion: number;
  balance_after: number;
}

export interface ScenarioResult {
  name: string;
  type: 'LOAN_AMORTIZATION' | 'SINKING_FUND';
  payment_amount: number;
  total_interest_paid: number;
  total_cost: number;
  fcf_impact_monthly: number;
  delta_vs_baseline: number | null;
  schedule: PeriodRow[];
}

export async function simulateScenarios(scenarios: ScenarioSpec[]): Promise<ScenarioResult[]> {
  const res = await fetch(`${API_URL}/planning/simulate`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify(scenarios),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || 'Simulation failed');
  }
  return res.json();
}

export interface AnnuityPeriodOut {
  id: number;
  period_number: number;
  payment_date: string;
  payment_amount: number;
  interest_portion: number;
  principal_portion: number;
  balance_after: number;
  is_paid: boolean;
  journal_entry_id: number | null;
}

export interface AnnuityScheduleOut {
  id: number;
  name: string;
  schedule_type: string;
  principal_amount: number;
  annual_rate: number;
  n_periods: number;
  payment_frequency: string;
  start_date: string;
  computed_payment: number;
  linked_journal_entry_id: number | null;
  linked_rule: LinkedRule | null;
  financing_contract: string | null;
  created_at: string;
  periods: AnnuityPeriodOut[];
}

export interface AnnuityScheduleListOut {
  id: number;
  name: string;
  schedule_type: string;
  principal_amount: number;
  annual_rate: number;
  n_periods: number;
  payment_frequency: string;
  start_date: string;
  computed_payment: number;
  created_at: string;
}

export async function commitSchedule(
  spec: ScenarioSpec,
  linked_journal_entry_id?: number,
): Promise<AnnuityScheduleOut> {
  const res = await fetch(`${API_URL}/planning/schedules`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify({ spec, linked_journal_entry_id: linked_journal_entry_id ?? null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || 'Commit failed');
  }
  return res.json();
}

export async function fetchSchedules(): Promise<AnnuityScheduleListOut[]> {
  const res = await fetch(`${API_URL}/planning/schedules`, { headers: getAuthHeader() });
  if (!res.ok) throw new Error('Failed to fetch schedules');
  return res.json();
}

export async function fetchSchedule(scheduleId: number): Promise<AnnuityScheduleOut> {
  const res = await fetch(`${API_URL}/planning/schedules/${scheduleId}`, { headers: getAuthHeader() });
  if (!res.ok) throw new Error('Failed to fetch schedule details');
  return res.json();
}

export async function deleteSchedule(scheduleId: number): Promise<void> {
  const res = await fetch(`${API_URL}/planning/schedules/${scheduleId}`, {
    method: 'DELETE',
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error('Failed to delete schedule');
}

// --- Portfolio Scenarios ---

export interface PortfolioStats {
  mean: number;
  median: number;
  std: number;
  min: number;
  max: number;
  skewness: number;
  kurtosis: number;
  percentile_5: number;
  percentile_25: number;
  percentile_50: number;
  percentile_75: number;
  percentile_95: number;
}

export interface DistributionData {
  count: number;
  stats: PortfolioStats;
  histogram_edges: number[];
  histogram_counts: number[];
  kde_x: number[];
  kde_y: number[];
  returns?: number[];
}

export interface ScenarioMetrics {
  horizon_years: number;
  pattern: string;
  lump_sum: DistributionData;
  dca: DistributionData;
}

export interface AllocationWeight {
  ticker: string;
  weight: number;
}

export interface AllocationResult {
  label: string;
  weights: AllocationWeight[];
  expected_return: number;
  volatility: number;
  sharpe_ratio: number;
}

export interface PortfolioOptimizationResult {
  tickers: string[];
  period_start: string;
  period_end: string;
  optimal: AllocationResult;
  alternatives: AllocationResult[];
}

export interface PortfolioScenariosResponse {
  optimization: PortfolioOptimizationResult;
  scenarios: ScenarioMetrics[];
  heatmap_data?: number[][];
}

export async function computePortfolioScenarios(
  tickers: string[],
  horizonsYears?: number[],
  monthlyDcaAmount?: number,
  rebalanceFreqMonths?: number,
): Promise<PortfolioScenariosResponse> {
  const res = await fetch(`${API_URL}/planning/portfolio-scenarios`, {
    method: 'POST',
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tickers,
      horizons_years: horizonsYears || [2, 5, 10, 15, 25],
      monthly_dca_amount: monthlyDcaAmount || 1000,
      rebalance_freq_months: rebalanceFreqMonths || 1,
      optimize: true,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || 'Portfolio scenarios computation failed');
  }
  return res.json();
}

// --- Statement Coverage ---

export interface StatementCell {
  month: string;              // "YYYY-MM"
  statement_id: number | null;
  status: string;             // present status, 'missing', or 'before_start'
}

export interface TargetCoverage {
  /** FinancialInstitution.id when target_type='INSTITUTION', FinancialProduct.id when 'PRODUCT' */
  target_id: number;
  /** Display name — e.g. "Tangerine (Consolidé)" or "Desjardins Boni Visa" */
  target_name: string;
  target_type: 'INSTITUTION' | 'PRODUCT';
  months: StatementCell[];
}

export interface StatementCoverage {
  all_months: string[];
  targets: TargetCoverage[];
}

export async function fetchStatementCoverage(): Promise<StatementCoverage> {
  const res = await fetch(`${API_URL}/banking/statement-coverage`, { headers: getAuthHeader() });
  if (!res.ok) throw new Error('Failed to fetch statement coverage');
  return res.json();
}

// --- Quality API ---

export type ConsistencySeverity = 'INFO' | 'WARNING' | 'ERROR';

export interface ConsistencyReportRun {
  id: number;
  family_id: string;
  trigger_source: string;
  status: string;
  scope: Record<string, unknown>;
  summary: {
    total_findings?: number;
    by_severity?: Record<string, number>;
    [key: string]: unknown;
  };
  error_message: string;
  started_at: string;
  finished_at: string | null;
  finding_count: number;
}

export interface ConsistencyReportFinding {
  id: number;
  run_id: number;
  severity: ConsistencySeverity;
  category: string;
  title: string;
  message: string;
  details: Record<string, unknown>;
  statement_import_id: number | null;
  staged_transaction_id: number | null;
  journal_entry_id: number | null;
  transaction_line_id: number | null;
  created_at: string;
}

export interface ConsistencyUnresolvedTransaction {
  id: number;
  statement_import_id: number;
  statement_import_label: string;
  financial_product_id: number | null;
  bank_date: string;
  raw_description: string;
  amount: string;
  status: string;
  predicted_account_id: number | null;
  journal_entry_id: number | null;
  cutoff_date: string;
  days_past_cutoff: number;
}

export async function fetchConsistencyRuns(limit = 25): Promise<ConsistencyReportRun[]> {
  const res = await fetch(`${API_URL}/quality/consistency-runs?limit=${limit}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error('Failed to fetch consistency runs');
  return res.json();
}

export async function triggerConsistencyRun(statement_ids?: number[]): Promise<ConsistencyReportRun> {
  const res = await fetch(`${API_URL}/quality/consistency-runs`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify({ statement_ids: statement_ids && statement_ids.length > 0 ? statement_ids : null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || 'Failed to trigger consistency run');
  }
  return res.json();
}

export async function fetchConsistencyFindings(
  runId: number,
  severity?: ConsistencySeverity,
): Promise<ConsistencyReportFinding[]> {
  const query = severity ? `?severity=${severity}` : '';
  const res = await fetch(`${API_URL}/quality/consistency-runs/${runId}/findings${query}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error('Failed to fetch consistency findings');
  return res.json();
}

export async function fetchConsistencyUnresolvedTransactions(runId: number): Promise<ConsistencyUnresolvedTransaction[]> {
  const res = await fetch(`${API_URL}/quality/consistency-runs/${runId}/unresolved-transactions`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error('Failed to fetch unresolved transactions');
  return res.json();
}

// --- Auth ---

export interface ProcessingLogEntry {
  ts: string;
  msg: string;
  level: 'info' | 'warn' | 'error' | 'success';
}

export interface StatementStatus {
  id: number;
  status: string;
  processing_log: ProcessingLogEntry[];
  validation_errors: any;
}

export async function fetchStatementStatus(importId: number): Promise<StatementStatus> {
  const res = await fetch(`${API_URL}/banking/statements/${importId}/status`, { headers: getAuthHeader() });
  if (!res.ok) throw new Error('Failed to fetch statement status');
  return res.json();
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
  confirmPassword: string
): Promise<void> {
  const res = await fetch(`${API_URL}/users/change-password`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to change password');
  }
}

// --- Analysis API ---

export async function fetchTopInsights() {
  const res = await fetch(`${API_URL}/analysis/insights/top/`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch top financial insights");
  }
  return res.json();
}

export async function triggerAnalyticsEngine() {
  const res = await fetch(`${API_URL}/analysis/engine/trigger/`, {
    method: "POST",
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to trigger analytics engine");
  }
  return res.json();
}

export interface AnalysisInsightRow {
  id: string;
  categoryName: string;
  insight_score: number;
  materiality_pct: number;
  processType: 'DETERMINISTIC' | 'STOCHASTIC' | 'EPISODIC';
  expertSummary: string;
  causal_volume_pct: number | null;
  causal_price_pct: number | null;
  projected_lower_bound?: number | null;
  projected_upper_bound?: number | null;
  benchmark_slope?: number | null;
  benchmark_classification?: 'REAL_GROWTH' | 'INFLATION_TRACKED' | 'EFFICIENCY_GAIN' | null;
}

export interface EngineStatus {
  status: "idle" | "syncing";
  last_computed_at: string | null;
  total_facts: number;
}

export interface LatestInsightsSnapshot {
  run_id: number | null;
  started_at: string | null;
  completed_at: string | null;
  total_insights: number;
  insights: AnalysisInsightRow[];
}

export async function getEngineStatus(): Promise<EngineStatus> {
  const res = await fetch(`${API_URL}/analysis/engine/status/`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch analytics engine status");
  }
  return res.json();
}

export async function fetchLatestInsightsSnapshot(): Promise<LatestInsightsSnapshot> {
  const res = await fetch(`${API_URL}/analysis/insights/latest/`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch latest insights snapshot");
  }
  return res.json();
}

// --- Asset expense categories & CPI inflation ---

export interface ExpenseCategory {
  id: number
  name: string
  statcan_vector_id: number | null
}

export async function fetchExpenseCategories(): Promise<ExpenseCategory[]> {
  const res = await fetch(`${API_URL}/assets/expense-categories`, {
    headers: getAuthHeader(),
  })
  if (!res.ok) throw new Error('Failed to fetch expense categories')
  return res.json()
}

export interface CpiRateResult {
  vector_id: number
  years: number
  cagr: number | null
  cagr_pct: number | null
}

export async function fetchCpiRate(vectorId: number, years = 10): Promise<CpiRateResult> {
  const res = await fetch(`${API_URL}/planning/cpi-rate/${vectorId}?years=${years}`, {
    headers: getAuthHeader(),
  })
  if (!res.ok) throw new Error('Failed to fetch CPI rate')
  return res.json()
}

// --- Projects API ---

export interface SinkingFundLineItem {
  id: number
  description: string
  today_price: number
  quantity: number
  total_today_price: number
  expense_category_id: number | null
  expense_category_name: string | null
  statcan_vector_id: number | null
  inflation_rate_override: number | null
  source_asset_id: number | null
  source_asset_name: string | null
}

export interface SinkingFundProject {
  id: number
  name: string
  target_date: string
  savings_start_date: string | null
  notes: string
  line_items: SinkingFundLineItem[]
  created_at: string
}

export interface SinkingFundProjectList {
  id: number
  name: string
  target_date: string
  savings_start_date: string | null
  line_item_count: number
  created_at: string
}

export interface ProjectIn {
  name: string
  target_date: string
  savings_start_date?: string | null
  notes?: string
}

export interface LineItemIn {
  description: string
  today_price: number
  quantity: number
  expense_category_id?: number | null
  inflation_rate_override?: number | null
  source_asset_id?: number | null
}

export async function fetchProjects(): Promise<SinkingFundProjectList[]> {
  const res = await fetch(`${API_URL}/projects/`, { headers: getAuthHeader() })
  if (!res.ok) throw new Error('Failed to fetch projects')
  return res.json()
}

export async function fetchProject(id: number): Promise<SinkingFundProject> {
  const res = await fetch(`${API_URL}/projects/${id}`, { headers: getAuthHeader() })
  if (!res.ok) throw new Error('Failed to fetch project')
  return res.json()
}

export async function createProject(data: ProjectIn): Promise<SinkingFundProject> {
  const res = await fetch(`${API_URL}/projects/`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create project')
  }
  return res.json()
}

export async function updateProject(id: number, data: ProjectIn): Promise<SinkingFundProject> {
  const res = await fetch(`${API_URL}/projects/${id}`, {
    method: 'PATCH',
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update project')
  }
  return res.json()
}

export async function deleteProject(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/projects/${id}`, {
    method: 'DELETE',
    headers: getAuthHeader(),
  })
  if (!res.ok) throw new Error('Failed to delete project')
}

export async function addLineItem(projectId: number, data: LineItemIn): Promise<SinkingFundProject> {
  const res = await fetch(`${API_URL}/projects/${projectId}/line-items`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to add line item')
  }
  return res.json()
}

export async function updateLineItem(projectId: number, itemId: number, data: LineItemIn): Promise<SinkingFundProject> {
  const res = await fetch(`${API_URL}/projects/${projectId}/line-items/${itemId}`, {
    method: 'PATCH',
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update line item')
  }
  return res.json()
}

// --- Loan Lifecycle API ---

export interface LoanSetupIn {
  purchase_description: string
  purchase_date: string
  purchase_price: number
  down_payment: number
  loan_amount: number
  asset_account_id: number
  cash_account_id: number
  loan_account_id?: number | null
  new_loan_account_name?: string | null
  schedule_name: string
  annual_rate: number
  amortization_years: number
  payment_frequency: 'MONTHLY' | 'BIWEEKLY' | 'WEEKLY' | 'ANNUALLY'
  schedule_start_date: string
}

export interface PayPeriodIn {
  cash_account_id: number
  loan_account_id: number
  interest_account_id: number
  payment_date?: string | null
}

export interface BulkPayIn {
  period_ids: number[]
  cash_account_id: number
  loan_account_id: number
  interest_account_id: number
}

export async function loanSetup(
  data: LoanSetupIn, 
  salesContract?: File | null,
  financingContract?: File | null
): Promise<AnnuityScheduleOut> {
  const formData = new FormData()
  
  // Flatten the data into the form data
  Object.entries(data).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      formData.append(key, String(value))
    }
  })

  if (salesContract) {
    formData.append('sales_contract', salesContract)
  }
  if (financingContract) {
    formData.append('financing_contract', financingContract)
  }

  const token = localStorage.getItem('access_token')
  const res = await fetch(`${API_URL}/planning/loan-setup`, {
    method: 'POST',
    headers: {
      "Authorization": token ? `Bearer ${token}` : ""
    },
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Loan setup failed')
  }
  return res.json()
}

export async function payPeriod(
  scheduleId: number,
  periodId: number,
  data: PayPeriodIn,
): Promise<AnnuityScheduleOut> {
  const res = await fetch(`${API_URL}/planning/schedules/${scheduleId}/periods/${periodId}/pay`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Payment recording failed')
  }
  return res.json()
}

export interface LinkedRule {
  id: number
  search_text: string
  min_amount: number | null
  max_amount: number | null
  merchant_name: string
  institution_id: number | null
}

export async function updateScheduleRule(
  scheduleId: number,
  searchText: string,
  institutionId?: number | null,
): Promise<AnnuityScheduleOut> {
  const res = await fetch(`${API_URL}/planning/schedules/${scheduleId}/rule`, {
    method: 'PATCH',
    headers: getAuthHeader(),
    body: JSON.stringify({ search_text: searchText, institution_id: institutionId ?? null }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update rule')
  }
  return res.json()
}

export async function bulkPayPeriods(scheduleId: number, data: BulkPayIn): Promise<AnnuityScheduleOut> {
  const res = await fetch(`${API_URL}/planning/schedules/${scheduleId}/bulk-pay`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Bulk payment failed')
  }
  return res.json()
}

export interface AccountFlat {
  id: number
  name: string
  account_type: string
  full_path?: string
}

export async function fetchAccountsWithType(): Promise<AccountFlat[]> {
  const res = await fetch(`${API_URL}/accounting/accounts-flat`, { headers: getAuthHeader() })
  if (!res.ok) throw new Error('Failed to fetch accounts')
  return res.json()
}

export async function deleteLineItem(projectId: number, itemId: number): Promise<SinkingFundProject> {
  const res = await fetch(`${API_URL}/projects/${projectId}/line-items/${itemId}`, {
    method: 'DELETE',
    headers: getAuthHeader(),
  })
  if (!res.ok) throw new Error('Failed to delete line item')
  return res.json()
}

// --- Assets ---

export interface CreateAssetIn {
  name: string
  purchase_value: number
  current_market_value: number
  purchase_date?: string | null
  account_id?: number | null
  account_name?: string | null
}

export interface CreateAssetOut {
  id: number
  name: string
}

export async function createAsset(data: CreateAssetIn): Promise<CreateAssetOut> {
  const res = await fetch(`${API_URL}/assets/`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(err.detail || 'Failed to create asset')
  }
  return res.json()
}

