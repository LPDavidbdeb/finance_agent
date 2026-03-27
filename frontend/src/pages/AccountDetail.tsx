import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { fetchAccountDetail, fetchAccountTransactions, fetchAccountsFlat, fetchMerchants } from '../api/client';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceLine, Cell
} from 'recharts';
import {
  ArrowLeft, Store, Layers, Loader2,
  TrendingUp, TrendingDown, Zap,
  Activity, BarChart3, Calendar, ChevronRight,
  ArrowRightLeft, PlusCircle, X
} from 'lucide-react';
import { InlineReroutePanel, RerouteMerchant } from '../components/InlineReroutePanel';
import { CreateRuleModal } from '../components/CreateRuleModal';

interface ChildAccount {
  id: number;
  name: string;
  account_type: string;
  balance: number;
}

interface Merchant {
  id: number;
  name: string;
  balance: number;
}

interface MonthlyCategory {
  child_id: number;
  child_name: string;
  amount: number;
}

interface MonthlyBreakdown {
  month: string;
  total: number;
  by_child: MonthlyCategory[];
}

interface CFAInsights {
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

interface YearlyTrend {
  year: number;
  total: number;
  monthly_avg: number;
  pct_of_income: number;
  breakdown: Record<string, number>;
}

interface AccountDetail {
  id: number;
  name: string;
  account_type: string;
  parent_id?: number;
  children: ChildAccount[];
  direct_merchants: Merchant[];
  insights: CFAInsights;
  monthly_breakdown: MonthlyBreakdown[];
  historical_trends: YearlyTrend[];
  avg_yearly_total: number;
  avg_monthly_avg: number;
}

const StatCard = ({ title, value, subValue, icon: Icon, color = "text-slate-900" }: any) => (
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

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// ---------------------------------------------------------------------------
// BannerTable — reusable transaction accordion with re-route + rule actions
// ---------------------------------------------------------------------------
interface BannerTableProps {
  transactions: any[];
  flatAccounts: any[];
  merchants: RerouteMerchant[];
  onTransactionUpdate: (entryId: number, updated: any) => void;
  onRuleSuccess: () => void;
}

const BannerTable: React.FC<BannerTableProps> = ({ transactions, flatAccounts, merchants, onTransactionUpdate, onRuleSuccess }) => {
  const [txSearch, setTxSearch] = useState('');
  const [expandedBanner, setExpandedBanner] = useState<string | null>(null);
  const [reroutingEntry, setReroutingEntry] = useState<number | null>(null);
  const [ruleModalTx, setRuleModalTx] = useState<any | null>(null);

  const bannerMap = new Map<string, { txs: any[]; total: number }>();
  transactions.forEach(tx => {
    if (!bannerMap.has(tx.description)) bannerMap.set(tx.description, { txs: [], total: 0 });
    const entry = bannerMap.get(tx.description)!;
    entry.txs.push(tx);
    entry.total += tx.amount;
  });
  const banners = Array.from(bannerMap.entries())
    .map(([name, { txs, total }]) => ({ name, txs, total, count: txs.length }))
    .sort((a, b) => b.count - a.count);
  const filtered = txSearch
    ? banners.filter(b => b.name.toLowerCase().includes(txSearch.toLowerCase()))
    : banners;

  return (
    <>
      <div className="flex justify-end px-4 py-3 border-b border-slate-100 bg-white">
        <input
          type="text"
          value={txSearch}
          onChange={e => setTxSearch(e.target.value)}
          placeholder="Search banners..."
          className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 w-48"
        />
      </div>
      {filtered.length === 0 ? (
        <p className="text-center py-12 text-slate-400 italic text-sm">No transactions found.</p>
      ) : (
        <table className="w-full text-sm">
          <thead className="bg-slate-50/50 border-b text-slate-500 text-xs uppercase font-bold tracking-wider">
            <tr>
              <th className="px-4 py-3 w-6"></th>
              <th className="px-4 py-3 text-left">Banner</th>
              <th className="px-4 py-3 text-center">Hits</th>
              <th className="px-4 py-3 text-right">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y bg-white">
            {filtered.map(banner => (
              <React.Fragment key={banner.name}>
                <tr
                  className="hover:bg-blue-50/40 cursor-pointer group transition-colors"
                  onClick={() => setExpandedBanner(expandedBanner === banner.name ? null : banner.name)}
                >
                  <td className="px-4 py-3 text-slate-400 group-hover:text-blue-500">
                    <ChevronRight className={`h-3.5 w-3.5 transition-transform ${expandedBanner === banner.name ? 'rotate-90' : ''}`} />
                  </td>
                  <td className="px-4 py-3 font-black text-slate-700 uppercase tracking-tight">{banner.name}</td>
                  <td className="px-4 py-3 text-center">
                    <Badge variant="secondary" className="text-[10px] rounded-full px-2">{banner.count}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-black text-slate-900">
                    ${banner.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                </tr>
                {expandedBanner === banner.name && (
                  <tr>
                    <td colSpan={4} className="p-0 bg-slate-50/80 border-b-2 border-blue-100">
                      <table className="w-full text-xs">
                        <thead className="border-b border-slate-200">
                          <tr className="text-slate-400">
                            <th className="px-10 py-2 text-left font-bold uppercase tracking-wider">Date</th>
                            <th className="px-4 py-2 text-left font-bold uppercase tracking-wider">From</th>
                            <th className="px-4 py-2 text-left font-bold uppercase tracking-wider">Routed To</th>
                            <th className="px-4 py-2 text-right font-bold uppercase tracking-wider">Amount</th>
                            <th className="px-4 py-2 text-right font-bold uppercase tracking-wider">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {banner.txs.map((tx: any) => (
                            <React.Fragment key={tx.journal_entry_id}>
                              <tr className="hover:bg-white transition-colors">
                                <td className="px-10 py-2.5 font-mono text-slate-500">{tx.date}</td>
                                <td className="px-4 py-2.5 text-slate-600">{tx.source_account}</td>
                                <td className="px-4 py-2.5">
                                  <Badge variant="outline" className="text-[10px] font-bold uppercase bg-white">
                                    {tx.routed_to}
                                  </Badge>
                                </td>
                                <td className="px-4 py-2.5 text-right font-mono font-black text-slate-900">
                                  ${tx.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                </td>
                                <td className="px-4 py-2.5 text-right">
                                  <div className="flex items-center justify-end gap-1">
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="h-6 text-[10px] gap-1 px-2"
                                      onClick={() => { setRuleModalTx(tx); setReroutingEntry(null); }}
                                    >
                                      <PlusCircle className="h-2.5 w-2.5" /> Rule
                                    </Button>
                                    <button
                                      onClick={() => {
                                        setReroutingEntry(reroutingEntry === tx.journal_entry_id ? null : tx.journal_entry_id);
                                      }}
                                      className="p-1 rounded hover:bg-blue-100 text-slate-400 hover:text-blue-600 transition-colors border border-slate-200"
                                      title="Re-route"
                                    >
                                      <ArrowRightLeft className="h-3 w-3" />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                              {reroutingEntry === tx.journal_entry_id && (
                                <tr>
                                  <td colSpan={5} className="px-10 py-3 bg-blue-50 border-l-4 border-blue-400">
                                    <InlineReroutePanel
                                      entryId={tx.journal_entry_id}
                                      flatAccounts={flatAccounts}
                                      merchants={merchants}
                                      onSuccess={(updated) => {
                                        onTransactionUpdate(tx.journal_entry_id, updated);
                                        setReroutingEntry(null);
                                      }}
                                      onCancel={() => setReroutingEntry(null)}
                                    />
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          ))}
                        </tbody>
                      </table>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      )}
      {ruleModalTx && (
        <CreateRuleModal
          isOpen={!!ruleModalTx}
          onClose={() => setRuleModalTx(null)}
          rawDescription={ruleModalTx.description}
          institutionId={ruleModalTx.institution_id || 0}
          onSuccess={() => { setRuleModalTx(null); onRuleSuccess(); }}
        />
      )}
    </>
  );
};

export const AccountDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentYear = new Date().getFullYear();
  const year = parseInt(searchParams.get('year') || currentYear.toString());
  const navigate = useNavigate();
  
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historyMode, setHistoryMode] = useState<'$' | '%'>('$');

  // Transaction review state
  const [transactions, setTransactions] = useState<any[]>([]);
  const [txLoading, setTxLoading] = useState(false);
  const [flatAccounts, setFlatAccounts] = useState<any[]>([]);
  const [merchants, setMerchants] = useState<RerouteMerchant[]>([]);
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);

  // Year list: always derived from the fixed historical map returned by the backend.
  // Ensures the dropdown and the chart cover the same anchored range.
  const allowedYears = useMemo(() => {
    if (account?.historical_trends?.length) {
      return account.historical_trends.map(t => t.year).sort((a, b) => b - a);
    }
    const years = [];
    for (let i = currentYear; i >= currentYear - 5; i--) years.push(i);
    return years;
  }, [account, currentYear]);

  useEffect(() => {
    if (id) {
      loadAccount(Number(id));
    }
  }, [id, year]);

  const loadAccount = async (accountId: number) => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchAccountDetail(accountId, year);
      setAccount(data);
    } catch (err: any) {
      setError(err.message || "Failed to load account details.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) {
      loadTransactions(Number(id));
    }
  }, [id, year]);

  useEffect(() => {
    fetchAccountsFlat().then(setFlatAccounts).catch(() => {});
    fetchMerchants().then(setMerchants).catch(() => {});
  }, []);

  const loadTransactions = async (accountId: number) => {
    try {
      setTxLoading(true);
      const data = await fetchAccountTransactions(accountId, year);
      setTransactions(data);
    } catch {
      setTransactions([]);
    } finally {
      setTxLoading(false);
    }
  };

  const handleTransactionUpdate = (entryId: number, updated: any) => {
    setTransactions(prev => prev.map(tx =>
      tx.journal_entry_id === entryId
        ? { ...tx, routed_to: updated.routed_to, routed_to_id: updated.routed_to_id }
        : tx
    ));
  };

  const handleYearChange = (newYear: string) => {
    setSearchParams({ year: newYear });
  };

  // Prepare chart data
  const chartData = useMemo(() => {
    if (!account?.monthly_breakdown) return [];
    return account.monthly_breakdown.map((m, idx) => {
      const row: any = { 
        name: MONTH_NAMES[idx],
        total: m.total 
      };
      m.by_child.forEach(c => {
        row[c.child_name] = c.amount;
      });
      return row;
    });
  }, [account]);

  const seriesNames = useMemo(() => {
    if (!account?.children) return [];
    return account.children.map(c => c.name);
  }, [account]);

  const colors = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', 
    '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#6366f1'
  ];

  if (loading) return <div className="flex justify-center p-20"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;
  if (error || !account) return <div className="p-20 text-center text-red-500">{error || "Account not found"}</div>;

  const { insights } = account;
  const growthColor = (insights.yoy_growth || 0) > 0 
    ? (account.account_type === 'REVENUE' ? 'text-emerald-600' : 'text-red-600') 
    : (account.account_type === 'REVENUE' ? 'text-red-600' : 'text-emerald-600');

  const monthlyAverage = account.monthly_breakdown.reduce((acc, m) => acc + m.total, 0) / 12;

  return (
    <div className="max-w-6xl mx-auto w-full pb-20">
      <div className="flex items-center gap-4 mb-6">
        <Button variant="ghost" onClick={() => navigate('/ledger')} size="sm" className="gap-2">
          <ArrowLeft className="h-4 w-4" /> Back to Ledger
        </Button>
        {account.parent_id && (
          <Button variant="ghost" onClick={() => navigate(`/dashboard/accounts/${account.parent_id}?year=${year}`)} size="sm" className="gap-2">
            Up to Parent
          </Button>
        )}
      </div>

      <div className="space-y-8">

      {/* Summary Bar — name + year selector + total, all in one line */}
      <div className="flex items-center justify-between bg-white px-6 py-3 rounded-xl shadow-sm border border-slate-200">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-black tracking-tighter text-slate-900 uppercase">{account.name}</h1>
          <Badge variant="outline" className="bg-slate-50 text-slate-400 border-slate-200 font-mono text-[10px]">
            {account.account_type}
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
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Total</p>
            <p className="text-xl font-black text-slate-900">
              ${insights.amount_current.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </p>
          </div>
          <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5">
            <Calendar className="h-3.5 w-3.5 text-slate-400" />
            <select
              value={year}
              onChange={(e) => handleYearChange(e.target.value)}
              className="text-sm font-black text-blue-600 bg-transparent focus:outline-none cursor-pointer"
            >
              {allowedYears.map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Context Cards */}
      {(() => {
        const monthlyAvgFocused = insights.amount_current / 12;
        const longRunMonthlyAvg = account.avg_monthly_avg;
        const monthlyDiff = monthlyAvgFocused - longRunMonthlyAvg;
        const peakMonth = account.monthly_breakdown.reduce(
          (best, m, idx) => m.total > best.total ? { total: m.total, idx } : best,
          { total: 0, idx: 0 }
        );
        const yoyDollars = insights.amount_current - insights.amount_previous;

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
              color={peakMonth.total > monthlyAvgFocused * 1.5 ? "text-amber-600" : "text-slate-900"}
            />
            <StatCard
              title="Year-over-Year"
              value={`${yoyDollars >= 0 ? '+' : ''}$${Math.abs(yoyDollars).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
              subValue={insights.yoy_growth !== null && insights.yoy_growth !== undefined
                ? `${(insights.yoy_growth * 100).toFixed(1)}% vs ${year - 1}`
                : `vs ${year - 1}`}
              icon={yoyDollars >= 0 ? TrendingUp : TrendingDown}
              color={yoyDollars > 0
                ? (account.account_type === 'REVENUE' ? 'text-emerald-600' : 'text-red-600')
                : (account.account_type === 'REVENUE' ? 'text-red-600' : 'text-emerald-600')}
            />
          </div>
        );
      })()}

          {/* Historical Year-over-Year Chart */}
          {account.historical_trends.length > 1 && (() => {
            const sortedTrends = account.historical_trends.slice().sort((a, b) => a.year - b.year);
            const isPct = historyMode === '%';
            const dataKey = isPct ? 'pct_of_income' : 'total';
            const avgValue = isPct
              ? sortedTrends.filter(t => t.pct_of_income > 0).reduce((s, t) => s + t.pct_of_income, 0) /
                (sortedTrends.filter(t => t.pct_of_income > 0).length || 1)
              : account.avg_yearly_total;

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
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={sortedTrends}
                        onClick={(e: any) => {
                          if (e?.activePayload?.[0]?.payload?.year) {
                            handleYearChange(String(e.activePayload[0].payload.year));
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
                          tickFormatter={(val) => isPct ? `${val.toFixed(0)}%` : `$${(val / 1000).toFixed(0)}k`}
                        />
                        <RechartsTooltip
                          cursor={{ fill: '#f8fafc' }}
                          contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' }}
                          formatter={(value: any) =>
                            isPct
                              ? [`${Number(value).toFixed(1)}% of income`, '']
                              : [`$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2 })}`, '']
                          }
                          labelFormatter={(label) => `${label}`}
                        />
                        <ReferenceLine
                          y={avgValue}
                          stroke="#94a3b8"
                          strokeDasharray="4 4"
                          label={{ position: 'right', value: 'Avg', fill: '#94a3b8', fontSize: 9, fontWeight: 'bold' }}
                        />
                        <Bar dataKey={dataKey} radius={[4, 4, 0, 0]} maxBarSize={60}>
                          {sortedTrends.map((entry) => (
                            <Cell
                              key={entry.year}
                              fill={entry.year === year ? '#3b82f6' : '#cbd5e1'}
                              opacity={entry.year === year ? 1 : 0.7}
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

          {/* What's inside — sub-account breakdown */}
          {account.children.length > 0 && (
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
                    {account.children.map(child => (
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

          {/* Month by Month */}
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
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={chartData}
                    onClick={(data) => { if (data?.activeLabel) setSelectedMonth(data.activeLabel as string); }}
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
                      tickFormatter={(val) => `$${val.toLocaleString()}`}
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
                        fill={colors[index % colors.length]}
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

          {/* Transaction Review — grouped by banner */}
          <Card className="shadow-sm">
            <CardHeader className="bg-slate-50/30 border-b border-slate-100">
              <CardTitle className="text-lg flex items-center gap-2">
                <Store className="h-5 w-5 text-blue-600" />
                Transactions — {year}
              </CardTitle>
              <CardDescription>
                Click a month bar above to drill into a specific month. Click a banner to expand, re-route or create a rule.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {txLoading ? (
                <div className="flex items-center justify-center py-12 gap-2 text-slate-400">
                  <Loader2 className="h-5 w-5 animate-spin" /> Loading...
                </div>
              ) : (
                <BannerTable
                  transactions={transactions}
                  flatAccounts={flatAccounts}
                  merchants={merchants}
                  onTransactionUpdate={handleTransactionUpdate}
                  onRuleSuccess={() => loadTransactions(Number(id))}
                />
              )}
            </CardContent>
          </Card>

          {/* Month drill-down modal */}
          {selectedMonth && (
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
              onClick={() => setSelectedMonth(null)}
            >
              <div
                className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[80vh] overflow-hidden flex flex-col"
                onClick={e => e.stopPropagation()}
              >
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/60">
                  <div>
                    <h2 className="text-lg font-black text-slate-900 uppercase tracking-tight flex items-center gap-2">
                      <BarChart3 className="h-5 w-5 text-blue-600" />
                      {selectedMonth} {year}
                    </h2>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {transactions.filter(tx => MONTH_NAMES[new Date(tx.date + 'T00:00:00').getMonth()] === selectedMonth).length} transactions · click a banner to expand
                    </p>
                  </div>
                  <button
                    onClick={() => setSelectedMonth(null)}
                    className="p-1.5 rounded hover:bg-slate-200 text-slate-400 transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <div className="overflow-y-auto flex-1">
                  <BannerTable
                    transactions={transactions.filter(tx =>
                      MONTH_NAMES[new Date(tx.date + 'T00:00:00').getMonth()] === selectedMonth
                    )}
                    flatAccounts={flatAccounts}
                    merchants={merchants}
                    onTransactionUpdate={handleTransactionUpdate}
                    onRuleSuccess={() => { setSelectedMonth(null); loadTransactions(Number(id)); }}
                  />
                </div>
              </div>
            </div>
          )}

      </div>{/* end space-y-8 */}
    </div>
  );
};
