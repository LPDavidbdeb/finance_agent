import React, { useMemo, useState } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceLine, Cell } from 'recharts';
import { ArrowLeft, Layers, Loader2, TrendingUp, TrendingDown, Zap, Activity, BarChart3, Calendar, ChevronRight } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { useAccountDetailData } from './account-detail/useAccountDetailData';
import { AccountTransactionReview } from './account-detail/AccountTransactionReview';
import { AccountDetailRecord } from './account-detail/types';

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const StatCard = ({ title, value, subValue, icon: Icon, color = 'text-slate-900' }: any) => (
  <Card className="shadow-sm border-slate-200">
    <CardHeader className="pb-2">
      <CardDescription className="text-[10px] uppercase font-bold tracking-widest flex items-center gap-2 text-slate-500">
        <Icon size={12} /> {title}
      </CardDescription>
      <CardTitle className={`text-2xl font-black ${color}`}>{value}</CardTitle>
      {subValue && <p className="text-[10px] text-slate-400 font-medium">{subValue}</p>}
    </CardHeader>
  </Card>
);

export const AccountDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentYear = new Date().getFullYear();
  const year = parseInt(searchParams.get('year') || currentYear.toString());
  const navigate = useNavigate();
  const [historyMode, setHistoryMode] = useState<'$' | '%'>('$');
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);

  const accountId = id ? Number(id) : null;
  const {
    account,
    loading,
    error,
    transactions,
    txLoading,
    flatAccounts,
    merchants,
    allowedYears,
    updateTransaction,
    refreshTransactions,
  } = useAccountDetailData(accountId, year);

  const chartData = useMemo(() => {
    if (!account?.monthly_breakdown) return [];

    return account.monthly_breakdown.map((month, index) => {
      const row: Record<string, number | string> = { name: MONTH_NAMES[index], total: month.total };
      month.by_child.forEach(child => {
        row[child.child_name] = child.amount;
      });
      return row;
    });
  }, [account]);

  const seriesNames = useMemo(() => {
    if (!account?.children) return [];
    return account.children.map(child => child.name);
  }, [account]);

  if (loading) {
    return (
      <div className="flex justify-center p-20">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !account) {
    return <div className="p-20 text-center text-red-500">{error || 'Account not found'}</div>;
  }

  const accountData = account as AccountDetailRecord;
  const { insights } = accountData;
  const trendForYear = accountData.historical_trends.find(trend => trend.year === year);
  const isAnnualized = year === currentYear && accountData.account_type === 'EXPENSE';
  const displayTotal = isAnnualized ? (trendForYear?.total || insights.amount_current) : insights.amount_current;

  const growthColor = (insights.yoy_growth || 0) > 0
    ? (accountData.account_type === 'REVENUE' ? 'text-emerald-600' : 'text-red-600')
    : (accountData.account_type === 'REVENUE' ? 'text-red-600' : 'text-emerald-600');

  const monthlyAverage = accountData.monthly_breakdown.reduce((sum, month) => sum + month.total, 0) / 12;

  return (
    <div className="max-w-6xl mx-auto w-full pb-20">
      <div className="flex items-center gap-4 mb-6">
        <Button variant="ghost" onClick={() => navigate('/ledger')} size="sm" className="gap-2">
          <ArrowLeft className="h-4 w-4" /> Back to Ledger
        </Button>
        {accountData.parent_id && (
          <Button variant="ghost" onClick={() => navigate(`/dashboard/accounts/${accountData.parent_id}?year=${year}`)} size="sm" className="gap-2">
            Up to Parent
          </Button>
        )}
      </div>

      <div className="space-y-8">
        <div className="flex items-center justify-between bg-white px-6 py-3 rounded-xl shadow-sm border border-slate-200">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black tracking-tighter text-slate-900 uppercase">{accountData.name}</h1>
            <Badge variant="outline" className="bg-slate-50 text-slate-400 border-slate-200 font-mono text-[10px]">
              {accountData.account_type}
            </Badge>
          </div>
          <div className="flex items-center gap-6">
            {insights.yoy_growth !== null && insights.yoy_growth !== undefined && (
              <div className={`flex items-center gap-1 text-sm font-bold ${growthColor}`}>
                {insights.yoy_growth > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {(insights.yoy_growth * 100).toFixed(1)}% YoY
              </div>
            )}
            <div className="text-right">
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{isAnnualized ? 'Est. Total' : 'Total'}</p>
              <p className="text-xl font-black text-slate-900">
                ${displayTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5">
              <Calendar className="h-3.5 w-3.5 text-slate-400" />
              <select
                value={year}
                onChange={e => setSearchParams({ year: e.target.value })}
                className="text-sm font-black text-blue-600 bg-transparent focus:outline-none cursor-pointer"
              >
                {allowedYears.map(allowedYear => (
                  <option key={allowedYear} value={allowedYear}>{allowedYear}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {(() => {
          const trend = accountData.historical_trends.find(item => item.year === year);
          const monthlyAvgFocused = trend ? trend.monthly_avg : insights.amount_current / 12;
          const longRunMonthlyAvg = accountData.avg_monthly_avg;
          const monthlyDiff = monthlyAvgFocused - longRunMonthlyAvg;
          const peakMonth = accountData.monthly_breakdown.reduce(
            (best, month, index) => month.total > best.total ? { total: month.total, idx: index } : best,
            { total: 0, idx: 0 }
          );
          const yoyDollars = isAnnualized
            ? (trend?.total || 0) - insights.amount_previous
            : insights.amount_current - insights.amount_previous;

          return (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <StatCard
                title="Monthly Average"
                value={`$${monthlyAvgFocused.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                subValue={`${monthlyDiff >= 0 ? '+' : ''}$${Math.abs(monthlyDiff).toLocaleString(undefined, { maximumFractionDigits: 0 })} vs long-run avg ($${longRunMonthlyAvg.toLocaleString(undefined, { maximumFractionDigits: 0 })}/mo)`}
                icon={BarChart3}
              />
              <StatCard
                title="Peak Month"
                value={`$${peakMonth.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                subValue={MONTH_NAMES[peakMonth.idx]}
                icon={Zap}
                color={peakMonth.total > monthlyAvgFocused * 1.5 ? 'text-amber-600' : 'text-slate-900'}
              />
              <StatCard
                title="Year-over-Year"
                value={`${yoyDollars >= 0 ? '+' : ''}$${Math.abs(yoyDollars).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                subValue={insights.yoy_growth !== null && insights.yoy_growth !== undefined
                  ? `${(insights.yoy_growth * 100).toFixed(1)}% ${isAnnualized ? '(annualized) ' : ''}vs ${year - 1}`
                  : `vs ${year - 1}`}
                icon={yoyDollars >= 0 ? TrendingUp : TrendingDown}
                color={yoyDollars > 0
                  ? (accountData.account_type === 'REVENUE' ? 'text-emerald-600' : 'text-red-600')
                  : (accountData.account_type === 'REVENUE' ? 'text-red-600' : 'text-emerald-600')}
              />
            </div>
          );
        })()}

        {accountData.historical_trends.length > 1 && (() => {
          const sortedTrends = accountData.historical_trends.slice().sort((a, b) => a.year - b.year);
          const isPct = historyMode === '%';
          const avgValue = isPct
            ? sortedTrends.filter(trend => trend.pct_of_income > 0).reduce((sum, trend) => sum + trend.pct_of_income, 0) /
              (sortedTrends.filter(trend => trend.pct_of_income > 0).length || 1)
            : accountData.avg_yearly_total;

          return (
            <Card className="shadow-sm overflow-hidden">
              <CardHeader className="bg-slate-50/30 border-b border-slate-100">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Activity className="h-5 w-5 text-blue-600" />
                      Historical Perspective
                    </CardTitle>
                    <CardDescription>
                      Click any bar to inspect that year.
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
                    {(['$', '%'] as const).map(mode => (
                      <button
                        key={mode}
                        onClick={() => setHistoryMode(mode)}
                        className={`px-3 py-1 rounded-md text-xs font-black transition-all ${
                          historyMode === mode
                            ? 'bg-white text-blue-600 shadow-sm'
                            : 'text-slate-400 hover:text-slate-600'
                        }`}
                      >
                        {mode === '%' ? '% of income' : '$ amount'}
                      </button>
                    ))}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-6">
                <div className="h-[200px] w-full">
                  <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
                    <BarChart
                      data={sortedTrends}
                      onClick={(event: any) => {
                        if (event?.activePayload?.[0]?.payload?.year) {
                          setSearchParams({ year: String(event.activePayload[0].payload.year) });
                        }
                      }}
                      style={{ cursor: 'pointer' }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis
                        dataKey="year"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 12, fontWeight: 700, fill: '#64748b' }}
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 10, fill: '#94a3b8' }}
                        tickFormatter={value => isPct ? `${Number(value).toFixed(0)}%` : `$${(Number(value) / 1000).toFixed(0)}k`}
                      />
                      <RechartsTooltip
                        cursor={{ fill: '#f8fafc' }}
                        contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' }}
                        formatter={(value: any, name: any) => {
                          const label = name === 'realized_total' ? 'Realized' : name === 'estimated_total' ? 'Estimated' : name;
                          return isPct
                            ? [`${Number(value).toFixed(1)}% of income`, label]
                            : [`$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2 })}`, label];
                        }}
                        labelFormatter={label => `${label}`}
                      />
                      <ReferenceLine
                        y={avgValue}
                        stroke="#94a3b8"
                        strokeDasharray="4 4"
                        label={{ position: 'right', value: 'Avg', fill: '#94a3b8', fontSize: 9, fontWeight: 'bold' }}
                      />
                      <Bar dataKey="realized_total" stackId="a" radius={[0, 0, 0, 0]} maxBarSize={60}>
                        {sortedTrends.map(entry => (
                          <Cell
                            key={entry.year}
                            fill={entry.year === year ? '#3b82f6' : '#cbd5e1'}
                            opacity={entry.year === year ? 1 : 0.7}
                          />
                        ))}
                      </Bar>
                      <Bar dataKey="estimated_total" stackId="a" radius={[4, 4, 0, 0]} maxBarSize={60}>
                        {sortedTrends.map(entry => (
                          <Cell
                            key={entry.year}
                            fill={entry.year === year ? '#3b82f6' : '#cbd5e1'}
                            opacity={0.4}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          );
        })()}

        {accountData.children.length > 0 && (
          <Card className="shadow-sm">
            <CardHeader className="bg-slate-50/30 border-b border-slate-100">
              <CardTitle className="text-lg flex items-center gap-2">
                <Layers className="h-5 w-5 text-blue-600" />
                What's inside
              </CardTitle>
              <CardDescription>Sub-categories and their share of the {year} total.</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead className="bg-slate-50/50 text-slate-500 font-medium">
                  <tr>
                    <th className="px-6 py-3 text-left">Category</th>
                    <th className="px-6 py-3 text-right">Total</th>
                    <th className="px-6 py-3 text-right">Share</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {accountData.children.map(child => (
                    <tr key={`child-${child.id}`} className="hover:bg-slate-50/50 group transition-colors">
                      <td className="px-6 py-4">
                        <Link
                          to={`/dashboard/accounts/${child.id}?year=${year}`}
                          className="font-black text-slate-700 hover:text-blue-600 flex items-center gap-2"
                        >
                          {child.name}
                          <ChevronRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </Link>
                      </td>
                      <td className="px-6 py-4 text-right font-mono font-bold text-slate-900">
                        ${child.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-blue-400"
                              style={{ width: `${insights.amount_current > 0 ? Math.min((child.balance / insights.amount_current) * 100, 100) : 0}%` }}
                            />
                          </div>
                          <span className="text-slate-500 font-medium w-10 text-right">
                            {insights.amount_current > 0 ? ((child.balance / insights.amount_current) * 100).toFixed(1) : '0.0'}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}

        <Card className="shadow-sm overflow-hidden">
          <CardHeader className="bg-slate-50/30 border-b border-slate-100">
            <CardTitle className="text-lg flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-blue-600" />
              Month by Month
            </CardTitle>
            <CardDescription>Where did the money go, and when.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="h-[350px] w-full">
              <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
                <BarChart
                  data={chartData}
                  onClick={(data) => {
                    if (data?.activeLabel) setSelectedMonth(data.activeLabel as string);
                  }}
                  style={{ cursor: 'pointer' }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    dataKey="name"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 12, fontWeight: 600, fill: '#64748b' }}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 10, fill: '#94a3b8' }}
                    tickFormatter={value => `$${Number(value).toLocaleString()}`}
                  />
                  <RechartsTooltip
                    cursor={{ fill: '#f8fafc' }}
                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' }}
                    formatter={(value: any, name: any) => [`$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2 })}`, name]}
                  />
                  <ReferenceLine
                    y={monthlyAverage}
                    stroke="#ef4444"
                    strokeDasharray="3 3"
                    label={{ position: 'right', value: 'Avg', fill: '#ef4444', fontSize: 10, fontWeight: 'bold' }}
                  />
                  {seriesNames.length > 0 ? seriesNames.map((name, index) => (
                    <Bar
                      key={name}
                      dataKey={name}
                      stackId="a"
                      fill={['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#6366f1'][index % 10]}
                      radius={[0, 0, 0, 0]}
                    />
                  )) : (
                    <Bar dataKey="total" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  )}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <AccountTransactionReview
          year={year}
          loading={txLoading}
          transactions={transactions}
          flatAccounts={flatAccounts}
          merchants={merchants}
          selectedMonth={selectedMonth}
          onSelectedMonthChange={setSelectedMonth}
          onTransactionUpdate={updateTransaction}
          onRuleSuccess={() => refreshTransactions()}
        />
      </div>
    </div>
  );
};
