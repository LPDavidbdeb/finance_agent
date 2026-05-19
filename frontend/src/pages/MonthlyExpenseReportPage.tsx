import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Download, Loader2 } from 'lucide-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import {
  fetchMonthlyExpenseOverview,
  fetchMonthlyExpenseOverviewPdf,
  MonthlyExpenseCategory,
  MonthlyExpensePoint,
  MonthlyExpenseReport,
} from '../api/client';
import { DrillDownModal } from '../components/DrillDownModal';

const COLORS = ['#2563eb', '#14b8a6', '#f97316', '#ef4444', '#0ea5e9', '#22c55e', '#8b5cf6', '#f59e0b'];
const currency = (value: number) => `$${Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

const MonthlyExpenseReportPage: React.FC = () => {
  const [data, setData] = useState<MonthlyExpenseReport | null>(null);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selection state
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);

  // Drill-down state
  const [drillDownDimension, setDrillDownDimension] = useState<string | null>(null);
  const [drillDownPeriod, setDrillDownPeriod] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await fetchMonthlyExpenseOverview(selectedMonth);
        setData(result);
        if (!selectedMonth && result.latest_month) {
          setSelectedMonth(result.latest_month);
        }
        if (result.categories.length > 0 && selectedCategoryId === null) {
          setSelectedCategoryId(result.categories[0].category_id);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load monthly expense report');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [selectedMonth]);

  const monthSummary = useMemo(() => {
    if (!data || !selectedMonth) return null;
    return data.summary_series.find(s => s.month === selectedMonth) || null;
  }, [data, selectedMonth]);

  const displayCategories = useMemo(() => {
    if (!data || !selectedMonth) return [];
    return data.categories.map(cat => {
      const point = cat.series.find(p => p.month === selectedMonth);
      const currentAmount = point ? point.amount : 0;
      const delta = currentAmount - cat.all_time_average;
      const deltaPct = cat.all_time_average !== 0 ? (delta / cat.all_time_average) * 100 : null;
      return {
        ...cat,
        current_month_amount: currentAmount,
        delta_vs_average: delta,
        delta_vs_average_pct: deltaPct
      };
    }).sort((a, b) => b.current_month_amount - a.current_month_amount);
  }, [data, selectedMonth]);

  const topFiveCategories = useMemo(() => displayCategories.slice(0, 5), [displayCategories]);

  const topFiveTransactions = useMemo(() => {
    if (!data?.top_transactions) return [];
    return data.top_transactions.slice(0, 5);
  }, [data]);

  const displayRevenueCategories = useMemo(() => {
    if (!data || !selectedMonth) return [];
    return data.revenue_categories.map(cat => {
      const point = cat.series.find(p => p.month === selectedMonth);
      const currentAmount = point ? point.amount : 0;
      const delta = currentAmount - cat.all_time_average;
      const deltaPct = cat.all_time_average !== 0 ? (delta / cat.all_time_average) * 100 : null;
      return {
        ...cat,
        current_month_amount: currentAmount,
        delta_vs_average: delta,
        delta_vs_average_pct: deltaPct
      };
    }).sort((a, b) => b.current_month_amount - a.current_month_amount);
  }, [data, selectedMonth]);

  const comparisonBars = useMemo(() => {
    if (!displayCategories) return [];
    return displayCategories.map((category) => ({
      category: category.category_name,
      current: category.current_month_amount,
      average: category.all_time_average,
      deltaPct: category.delta_vs_average_pct ?? 0,
    }));
  }, [displayCategories]);

  const chartData = useMemo(() => {
    if (!data) return [];
    let runningTotal = 0;
    return data.summary_series.map(s => {
      runningTotal += s.savings;
      return {
        ...s,
        cumulative: runningTotal
      };
    });
  }, [data]);

  const selectedCategory = useMemo(() => {
    if (!data || selectedCategoryId === null) return null;
    return data.categories.find((category) => category.category_id === selectedCategoryId) ?? null;
  }, [data, selectedCategoryId]);

  const categorySeriesData = useMemo(() => {
    if (!selectedCategory) return [];
    return selectedCategory.series.map((point) => ({
      month: point.month,
      value: point.amount,
      average: selectedCategory.all_time_average,
    }));
  }, [selectedCategory]);

  const stackedSeries = useMemo(() => {
    if (!data || data.categories.length === 0) return [];

    const monthMap = new Map<string, Record<string, string | number>>();
    data.totals_series.forEach((point: MonthlyExpensePoint) => {
      monthMap.set(point.month, { month: point.month });
    });

    data.categories.forEach((category: MonthlyExpenseCategory) => {
      category.series.forEach((point) => {
        const row = monthMap.get(point.month);
        if (row) {
          row[category.category_name] = point.amount;
        }
      });
    });

    return Array.from(monthMap.values());
  }, [data]);

  if (loading) {
    return (
      <div className="flex min-h-[360px] items-center justify-center">
        <Loader2 className="h-10 w-10 animate-spin text-slate-500" />
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Monthly Expense Report</CardTitle>
          <CardDescription>Unable to load data</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-red-600">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (!data || data.categories.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Monthly Expense Report</CardTitle>
          <CardDescription>No expense history available yet.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const handleDownloadPdf = async () => {
    try {
      setDownloadingPdf(true);
      const blob = await fetchMonthlyExpenseOverviewPdf(selectedMonth);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `monthly-expense-report-${selectedMonth || data.latest_month || 'latest'}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || 'Failed to generate PDF report');
    } finally {
      setDownloadingPdf(false);
    }
  };

  return (
    <div className="space-y-6 pb-10">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Monthly Financial Report</h1>
          <p className="mt-2 text-sm text-slate-500">
          Full monthly series by category and comparison against all-time monthly averages.
          {selectedMonth ? ` Viewing: ${selectedMonth}.` : ''}
          {selectedMonth !== data.latest_month && (
            <button 
              onClick={() => setSelectedMonth(data.latest_month)}
              className="ml-2 text-blue-600 hover:underline font-medium"
            >
              Back to latest
            </button>
          )}
          </p>
        </div>
        <button
          type="button"
          onClick={handleDownloadPdf}
          disabled={downloadingPdf}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Download className="h-4 w-4" />
          {downloadingPdf ? 'Preparing PDF...' : 'Download PDF'}
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card 
          className={`cursor-pointer transition-all group ${selectedMonth === data.latest_month ? 'hover:border-blue-500' : 'border-blue-200 ring-1 ring-blue-100 shadow-sm'}`}
          onClick={() => {
            if (selectedMonth) {
              setDrillDownDimension('revenue');
              setDrillDownPeriod(selectedMonth);
            }
          }}
        >
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500 uppercase tracking-wider flex justify-between">
              {selectedMonth === data.latest_month ? 'Latest' : selectedMonth} Revenue
              <span className="text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] font-bold">VERIFY</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900">{currency(monthSummary?.revenue || 0)}</div>
            <div className="mt-1 flex items-center justify-between">
              <p className="text-xs text-slate-500">Inflow for {selectedMonth}</p>
              <p className="text-xs font-semibold text-slate-400">Avg: {currency(data.avg_revenue)}</p>
            </div>
            <div className="mt-3 space-y-1 border-t pt-2">
              {displayRevenueCategories.slice(0, 3).map(cat => (
                <div key={cat.category_id} className="flex justify-between text-[10px]">
                  <span className="text-slate-500 truncate mr-2">{cat.category_name}</span>
                  <span className="text-slate-900 font-medium">{currency(cat.current_month_amount)} <span className="text-slate-400 font-normal">(avg {currency(cat.all_time_average)})</span></span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card 
          className={`cursor-pointer transition-all group ${selectedMonth === data.latest_month ? 'hover:border-orange-500' : 'border-orange-200 ring-1 ring-orange-100 shadow-sm'}`}
          onClick={() => {
            if (selectedMonth) {
              setDrillDownDimension('expenses');
              setDrillDownPeriod(selectedMonth);
            }
          }}
        >
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500 uppercase tracking-wider flex justify-between">
              {selectedMonth === data.latest_month ? 'Latest' : selectedMonth} Expenses
              <span className="text-orange-500 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] font-bold">VERIFY</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900">{currency(monthSummary?.expenses || 0)}</div>
            <div className="mt-1 flex items-center justify-between">
              <p className="text-xs text-slate-500">Outflow for {selectedMonth}</p>
              <p className="text-xs font-semibold text-slate-400">Avg: {currency(data.avg_expenses)}</p>
            </div>
            <div className="mt-3 space-y-1 border-t pt-2">
              {displayCategories.slice(0, 3).map(cat => (
                <div key={cat.category_id} className="flex justify-between text-[10px]">
                  <span className="text-slate-500 truncate mr-2">{cat.category_name}</span>
                  <span className="text-slate-900 font-medium">{currency(cat.current_month_amount)} <span className="text-slate-400 font-normal">(avg {currency(cat.all_time_average)})</span></span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card className={selectedMonth !== data.latest_month ? 'border-emerald-200 ring-1 ring-emerald-100 shadow-sm' : ''}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500 uppercase tracking-wider">
              {selectedMonth === data.latest_month ? 'Latest' : selectedMonth} Savings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">
              {currency(monthSummary?.savings || 0)}
            </div>
            <div className="mt-1 flex items-center justify-between">
              <p className="text-xs text-slate-500">Net surplus for {selectedMonth}</p>
              <p className="text-xs font-semibold text-slate-400">Avg: {currency(data.avg_savings)}</p>
            </div>
            <div className="mt-3 pt-2 border-t">
              <div className="flex justify-between text-[10px]">
                <span className="text-slate-500">Savings Rate</span>
                <span className="text-emerald-600 font-bold">
                  {monthSummary && monthSummary.revenue > 0 ? ((monthSummary.savings / monthSummary.revenue) * 100).toFixed(1) : '0.0'}%
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Top 5 Expense Categories</CardTitle>
            <CardDescription>
              Largest categories for {selectedMonth}.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {topFiveCategories.length > 0 ? topFiveCategories.map((category, index) => (
              <Link
                key={category.category_id}
                to={`/dashboard/accounts/${category.category_id}?year=${selectedMonth?.slice(0, 4) ?? new Date().getFullYear()}`}
                className="flex items-start justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 transition-colors hover:border-blue-400 hover:bg-blue-50"
              >
                <div className="min-w-0 pr-3">
                  <p className="text-sm font-semibold text-slate-900">{index + 1}. {category.category_name}</p>
                  <p className="text-xs text-slate-500">Avg {currency(category.all_time_average)} per month</p>
                  <p className={`text-xs ${category.delta_vs_average >= 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                    {category.delta_vs_average_pct !== null ? `${category.delta_vs_average_pct.toFixed(1)}% vs avg` : 'n/a vs avg'}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-slate-900">{currency(category.current_month_amount)}</p>
                </div>
              </Link>
            )) : (
              <p className="text-sm text-slate-500">No category data available for this month.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top 5 Transactions</CardTitle>
            <CardDescription>Largest individual expense transactions in the latest month.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {topFiveTransactions.length > 0 ? topFiveTransactions.map((transaction, index) => (
              <Link
                key={transaction.journal_entry_id}
                to={transaction.statement_id
                  ? `/dashboard/statements/${transaction.statement_id}${transaction.staged_transaction_id ? `?highlight_transaction=${transaction.staged_transaction_id}` : `?highlight=${transaction.journal_entry_id}`}`
                  : `/dashboard/accounts/${transaction.category_id}?year=${selectedMonth?.slice(0, 4) ?? new Date().getFullYear()}`}
                className="flex items-start justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 transition-colors hover:border-blue-400 hover:bg-blue-50"
              >
                <div className="min-w-0 pr-3">
                  <p className="truncate text-sm font-semibold text-slate-900">{index + 1}. {transaction.merchant_name || transaction.description}</p>
                  <p className="truncate text-xs text-slate-500">{transaction.description}</p>
                  <p className="text-xs text-slate-400">{transaction.category_name}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-slate-900">{currency(transaction.amount)}</p>
                  <p className="text-xs text-slate-500">{transaction.date}</p>
                </div>
              </Link>
            )) : (
              <p className="text-sm text-slate-500">No transactions available for the latest month.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <DrillDownModal
        isOpen={!!drillDownDimension && !!drillDownPeriod}
        onClose={() => {
          setDrillDownDimension(null);
          setDrillDownPeriod(null);
        }}
        dimension={drillDownDimension || ''}
        period={drillDownPeriod || ''}
      />

      <Card>
        <CardHeader>
          <CardTitle>Cash Flow Evolution</CardTitle>
          <CardDescription>Click a month to update the report view. Currently showing: {selectedMonth}.</CardDescription>
        </CardHeader>
        <CardContent className="h-[350px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart 
              data={data.summary_series}
              onClick={(e) => {
                if (e && e.activeLabel) {
                  setSelectedMonth(String(e.activeLabel));
                }
              }}
              style={{ cursor: 'pointer' }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis tickFormatter={currency} />
              <Tooltip formatter={(value: any) => currency(Number(value))} />
              <Legend />
              <Bar dataKey="revenue" fill="#14b8a6" name="Revenue" radius={[4, 4, 0, 0]} />
              <Bar dataKey="expenses" fill="#f97316" name="Expenses" radius={[4, 4, 0, 0]} />
              <Line type="monotone" dataKey="savings" stroke="#2563eb" strokeWidth={3} name="Monthly Savings" dot={{ r: 4, stroke: '#2563eb', strokeWidth: 2, fill: '#fff' }} activeDot={{ r: 6 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Wealth Builder</CardTitle>
          <CardDescription>The cumulative effect of your monthly savings over time.</CardDescription>
        </CardHeader>
        <CardContent className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis tickFormatter={currency} />
              <Tooltip 
                formatter={(value: any) => [currency(Number(value)), 'Total Wealth Growth']}
                labelFormatter={(label) => `As of ${label}`}
              />
              <Legend />
              <Line 
                type="stepAfter" 
                dataKey="cumulative" 
                stroke="#8b5cf6" 
                strokeWidth={4} 
                name="Total Wealth Growth" 
                dot={{ r: 3, fill: '#8b5cf6' }} 
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Current Month vs All-Time Average</CardTitle>
          <CardDescription>Comparing current month spend (blue) against historical average (grey) for each category.</CardDescription>
        </CardHeader>
        <CardContent className="h-[420px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={comparisonBars} layout="vertical" margin={{ top: 5, right: 30, left: 150, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tickFormatter={currency} />
              <YAxis type="category" dataKey="category" width={145} />
              <Tooltip
                formatter={(value: any) => currency(Number(value))}
              />
              <Legend />
              <Bar dataKey="current" fill="#2563eb" name="Current month" />
              <Bar dataKey="average" fill="#94a3b8" name="All-time average" />
            </ComposedChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <CardTitle>Category Time Series</CardTitle>
              <CardDescription>
                {selectedCategory ? `${selectedCategory.category_name} with all-time monthly average overlay.` : 'Select a category.'}
              </CardDescription>
            </div>
            <label className="flex flex-col gap-1 text-xs font-medium text-slate-500 md:w-[280px]">
              Category
              <select
                value={selectedCategoryId ?? ''}
                onChange={(event) => setSelectedCategoryId(Number(event.target.value))}
                className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm outline-none transition-colors focus:border-blue-500"
              >
                {data.categories.map((category) => (
                  <option key={category.category_id} value={category.category_id}>
                    {category.category_name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </CardHeader>
        <CardContent className="h-[360px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={categorySeriesData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis tickFormatter={currency} />
              <Tooltip formatter={(value: any, name: any) => [currency(Number(value)), name === 'value' ? 'Monthly expense' : 'All-time average']} />
              <Legend />
              <Line type="monotone" dataKey="value" stroke="#0f766e" strokeWidth={2.5} dot={false} name="Monthly expense" />
              <Line type="monotone" dataKey="average" stroke="#ef4444" strokeDasharray="5 5" dot={false} name="All-time average" />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>All Categories Over Time</CardTitle>
          <CardDescription>Stacked view of monthly category spend.</CardDescription>
        </CardHeader>
        <CardContent className="h-[380px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={stackedSeries}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis tickFormatter={currency} />
              <Tooltip formatter={(value: any) => currency(Number(value))} />
              <Legend />
              {data.categories.map((category, index) => (
                <Bar
                  key={category.category_id}
                  dataKey={category.category_name}
                  stackId="expenses"
                  fill={COLORS[index % COLORS.length]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

    </div>
  );
};

export default MonthlyExpenseReportPage;
