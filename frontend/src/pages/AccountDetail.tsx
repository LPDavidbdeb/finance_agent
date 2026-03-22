import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { fetchAccountDetail } from '../api/client';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';
import { 
  ArrowLeft, Store, Layers, Loader2, 
  TrendingUp, TrendingDown, Target, Zap, AlertTriangle, CheckCircle2,
  Clock, PieChart, Activity, BarChart3
} from 'lucide-react';

interface ChildAccount {
  id: number;
  name: string;
  account_type: string;
}

interface Merchant {
  id: number;
  name: string;
  balance: number;
}

interface YearlyTrend {
  year: number;
  total: number;
  monthly_avg: number;
  breakdown: Record<string, number>;
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

interface AccountDetail {
  id: number;
  name: string;
  account_type: string;
  parent_id?: number;
  children: ChildAccount[];
  merchants: Merchant[];
  insights: CFAInsights;
  historical_trends: YearlyTrend[];
  avg_yearly_total: number;
  avg_monthly_avg: number;
}

const StatCard = ({ title, value, subValue, icon: Icon, color = "text-slate-900" }: any) => (
  <Card className="shadow-sm border-slate-200">
    <CardHeader className="pb-2">
      <CardDescription className="text-[10px] uppercase font-bold tracking-widest flex items-center gap-2">
        <Icon size={12} /> {title}
      </CardDescription>
      <CardTitle className={`text-2xl font-black ${color}`}>{value}</CardTitle>
      {subValue && <p className="text-[10px] text-slate-400 font-medium">{subValue}</p>}
    </CardHeader>
  </Card>
);

export const AccountDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const currentYear = new Date().getFullYear();
  const year = parseInt(searchParams.get('year') || currentYear.toString());
  const navigate = useNavigate();
  
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  if (loading) return <div className="flex justify-center p-20"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;
  if (error || !account) return <div className="p-20 text-center text-red-500">{error || "Account not found"}</div>;

  // Prepare data for stacked charts
  const allCategoryNames = Array.from(new Set(account.historical_trends.flatMap(t => Object.keys(t.breakdown))));
  const colors = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', 
    '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#6366f1'
  ];
  const colorMap = Object.fromEntries(allCategoryNames.map((cat, i) => [cat, colors[i % colors.length]]));

  const stackedYearlyData = account.historical_trends.map(t => ({
    year: t.year,
    ...t.breakdown
  }));

  const stackedMonthlyData = account.historical_trends.map(t => {
    const monthlyBreakdown: any = { year: t.year };
    Object.entries(t.breakdown).forEach(([name, val]) => {
      monthlyBreakdown[name] = val / 12;
    });
    return monthlyBreakdown;
  });

  const { insights } = account;
  const growthColor = (insights.yoy_growth || 0) > 0 
    ? (account.account_type === 'REVENUE' ? 'text-emerald-600' : 'text-red-600') 
    : (account.account_type === 'REVENUE' ? 'text-red-600' : 'text-emerald-600');

  return (
    <div className="space-y-8 max-w-6xl mx-auto w-full pb-20">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/ledger')} size="sm" className="gap-2">
            <ArrowLeft className="h-4 w-4" /> Back to Ledger
          </Button>
          {account.parent_id && (
            <Button variant="ghost" onClick={() => navigate(`/dashboard/accounts/${account.parent_id}?year=${year}`)} size="sm" className="gap-2">
              Up to Parent
            </Button>
          )}
        </div>
        <Badge variant="outline" className="px-3 py-1 text-sm font-medium">
          Fiscal Year {year}
        </Badge>
      </div>

      {/* Summary Bar */}
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Badge variant="outline" className="bg-slate-50 text-slate-500 border-slate-200 font-mono">
                {account.account_type}
              </Badge>
              <Badge className={`${
                insights.health_tag === 'stable' ? 'bg-emerald-100 text-emerald-700' : 
                insights.health_tag === 'drifting' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'
              } border-none uppercase text-[10px] font-bold`}>
                {insights.health_tag}
              </Badge>
            </div>
            <h1 className="text-5xl font-black tracking-tighter text-slate-900 uppercase">
              {account.name}
            </h1>
          </div>
          <div className="text-right">
            <p className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-1">Current Period</p>
            <p className="text-5xl font-black text-slate-900">
              ${insights.amount_current.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </p>
            {insights.yoy_growth !== null && (
              <p className={`text-sm font-bold flex items-center justify-end gap-1 ${growthColor}`}>
                {insights.yoy_growth! > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {(insights.yoy_growth! * 100).toFixed(1)}% YoY
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Universal Context Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard 
          title="Materiality" 
          value={`${(insights.share_of_parent * 100).toFixed(1)}%`} 
          subValue="of parent branch" 
          icon={PieChart} 
        />
        <StatCard 
          title="Inflow Impact" 
          value={`${(insights.share_of_total_inflow * 100).toFixed(1)}%`} 
          subValue="of household revenue" 
          icon={Activity} 
        />
        <StatCard 
          title="Volatility" 
          value={`$${insights.volatility_score.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} 
          subValue="Monthly Std Dev" 
          icon={Zap} 
        />
        <StatCard 
          title="Concentration" 
          value={`${(insights.concentration_top_1 * 100).toFixed(0)}%`} 
          subValue="Top contributor share" 
          icon={Target} 
          color={insights.concentration_top_1 > 0.5 ? "text-amber-600" : "text-slate-900"}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left: Decomposition & Drivers */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* Yearly Trends Visualization */}
          <Card className="shadow-sm overflow-hidden">
            <CardHeader className="bg-slate-50/30 border-b border-slate-100 flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-blue-600" />
                  Historical Performance
                </CardTitle>
                <CardDescription>Visualizing structural mix and category intensity over time.</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="pt-6 space-y-12">
              {/* Yearly Total Stacked Chart */}
              <div className="space-y-4">
                <div className="flex justify-between items-end px-2">
                  <div>
                    <p className="text-[10px] font-bold uppercase text-slate-400 tracking-widest">Yearly Total Volume</p>
                    <p className="text-xs text-slate-500 italic">Stacked by sub-categories</p>
                  </div>
                  <p className="text-[10px] font-medium text-red-500">Global Mean: ${account.avg_yearly_total.toLocaleString()}</p>
                </div>
                <div className="h-[300px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stackedYearlyData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis 
                        dataKey="year" 
                        axisLine={false} 
                        tickLine={false} 
                        tick={{ fontSize: 12, fontWeight: 600, fill: '#64748b' }}
                      />
                      <YAxis 
                        axisLine={false} 
                        tickLine={false} 
                        tick={{ fontSize: 10, fill: '#94a3b8' }}
                        tickFormatter={(val) => `$${(val / 1000).toFixed(0)}k`}
                      />
                      <RechartsTooltip 
                        cursor={{ fill: '#f8fafc' }}
                        contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' }}
                        formatter={(value: any) => [`$${value.toLocaleString()}`, ""]}
                      />
                      <ReferenceLine y={account.avg_yearly_total} stroke="#ef4444" strokeDasharray="3 3" />
                      {allCategoryNames.map(cat => (
                        <Bar 
                          key={cat} 
                          dataKey={cat} 
                          stackId="a" 
                          fill={colorMap[cat]} 
                          radius={[0, 0, 0, 0]}
                          barSize={60}
                        />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Monthly Average Stacked Chart */}
              <div className="space-y-4">
                <div className="flex justify-between items-end px-2 border-t border-slate-50 pt-6">
                  <div>
                    <p className="text-[10px] font-bold uppercase text-slate-400 tracking-widest">Monthly Velocity Average</p>
                    <p className="text-xs text-slate-500 italic">Normalized category intensity</p>
                  </div>
                  <p className="text-[10px] font-medium text-red-500">Average Velocity: ${account.avg_monthly_avg.toLocaleString()}</p>
                </div>
                <div className="h-[250px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stackedMonthlyData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis 
                        dataKey="year" 
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
                        formatter={(value: any) => [`$${value.toLocaleString()}`, ""]}
                      />
                      <ReferenceLine y={account.avg_monthly_avg} stroke="#ef4444" strokeDasharray="3 3" />
                      {allCategoryNames.map(cat => (
                        <Bar 
                          key={cat} 
                          dataKey={cat} 
                          stackId="b" 
                          fill={colorMap[cat]} 
                          radius={[0, 0, 0, 0]}
                          barSize={40}
                        />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Driver Decomposition */}
          <Card className="shadow-sm">
            <CardHeader className="bg-slate-50/30 border-b border-slate-100">
              <CardTitle className="text-lg flex items-center gap-2">
                <Layers className="h-5 w-5 text-blue-600" />
                Driver Decomposition
              </CardTitle>
              <CardDescription>Hierarchical breakdown of spending/income sources.</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50/50 text-slate-500 font-medium">
                    <tr>
                      <th className="px-6 py-3 text-left">Sub-Account / Source</th>
                      <th className="px-6 py-3 text-right">Balance</th>
                      <th className="px-6 py-3 text-right">Share</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {account.children.length === 0 && account.merchants.length === 0 ? (
                      <tr><td colSpan={3} className="p-10 text-center text-slate-400 italic">No detailed drivers found.</td></tr>
                    ) : (
                      <>
                        {account.children.map(child => (
                          <tr key={`child-${child.id}`} className="hover:bg-slate-50/50">
                            <td className="px-6 py-4">
                              <Link to={`/dashboard/accounts/${child.id}?year=${year}`} className="font-bold text-slate-700 hover:text-blue-600">
                                {child.name}
                              </Link>
                            </td>
                            <td className="px-6 py-4 text-right font-mono">$0.00</td>
                            <td className="px-6 py-4 text-right text-slate-400 text-xs">--</td>
                          </tr>
                        ))}
                        {account.merchants.map(merchant => (
                          <tr key={`merch-${merchant.id}`} className="hover:bg-slate-50/50">
                            <td className="px-6 py-4 flex items-center gap-2">
                              <Store size={14} className="text-slate-400" />
                              <Link to={`/dashboard/merchants/${merchant.id}`} className="font-medium text-slate-600">
                                {merchant.name}
                              </Link>
                            </td>
                            <td className="px-6 py-4 text-right font-mono font-bold">
                              ${merchant.balance.toLocaleString()}
                            </td>
                            <td className="px-6 py-4 text-right text-slate-400 text-xs">
                              {((merchant.balance / insights.amount_current) * 100).toFixed(1)}%
                            </td>
                          </tr>
                        ))}
                      </>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Action & Risk Panel */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="border-emerald-100 bg-emerald-50/20 shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-emerald-800 flex items-center gap-2 text-sm uppercase tracking-wider">
                  <CheckCircle2 size={16} /> Performance Highlights
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {insights.green_flag ? (
                  <div>
                    <p className="font-bold text-slate-900">{insights.green_flag.title}</p>
                    <p className="text-xs text-slate-600 leading-relaxed">{insights.green_flag.detail}</p>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">No significant efficiency gains detected in this period.</p>
                )}
              </CardContent>
            </Card>

            <Card className="border-red-100 bg-red-50/20 shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-red-800 flex items-center gap-2 text-sm uppercase tracking-wider">
                  <AlertTriangle size={16} /> Risk Exposure
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {insights.red_flag ? (
                  <div>
                    <p className="font-bold text-slate-900">{insights.red_flag.title}</p>
                    <p className="text-xs text-slate-600 leading-relaxed">{insights.red_flag.detail}</p>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">No critical risks identified for this node.</p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Right: CFA Lenses */}
        <div className="space-y-6">
          <Card className="shadow-md border-blue-100 bg-white">
            <CardHeader className="border-b border-slate-50 bg-slate-50/30">
              <CardTitle className="text-lg">CFA Lenses</CardTitle>
              <CardDescription>Deep analysis of branch dynamics.</CardDescription>
            </CardHeader>
            <CardContent className="pt-6 space-y-8">
              {/* Drift Lens */}
              {insights.drift_spread !== undefined && (
                <div className="space-y-2">
                  <p className="text-[10px] font-black uppercase text-blue-600 tracking-widest">Operational Drift</p>
                  <div className="flex justify-between items-end">
                    <p className="text-2xl font-black">{((insights.drift_spread || 0) * 100).toFixed(1)}%</p>
                    <Badge variant="outline" className={insights.drift_spread && insights.drift_spread > 0.05 ? "text-red-600 border-red-200" : "text-emerald-600 border-emerald-200"}>
                      {insights.drift_spread && insights.drift_spread > 0.05 ? "Efficiency Loss" : "Positive Drift"}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    This category is growing {Math.abs((insights.drift_spread || 0) * 100).toFixed(1)}% {insights.drift_spread && insights.drift_spread > 0 ? "faster" : "slower"} than household income.
                  </p>
                </div>
              )}

              {/* Optimization Lens */}
              <div className="space-y-2">
                <p className="text-[10px] font-black uppercase text-emerald-600 tracking-widest">Optimization Room</p>
                <p className="text-2xl font-black">${(insights.optimization_headroom || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
                <p className="text-xs text-slate-500 leading-relaxed">
                  A 5% reduction in top vendor relationships yields this annual savings potential.
                </p>
              </div>

              {/* Burn Lens */}
              {insights.burn_coverage_days !== undefined && (
                <div className="space-y-2">
                  <p className="text-[10px] font-black uppercase text-amber-600 tracking-widest">Asset Burn Rate</p>
                  <p className="text-2xl font-black">{(insights.burn_coverage_days || 0).toFixed(0)} Days</p>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Household total assets could fund this specific branch for this many days in a shock scenario.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="bg-slate-900 text-white shadow-xl">
            <CardHeader>
              <CardTitle className="text-xs uppercase tracking-tighter text-slate-400">Strategic Next Action</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-lg font-bold leading-tight">
                {insights.strategic_action?.action}
              </p>
              <div className="flex items-center justify-between pt-4 border-t border-slate-800">
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <Clock size={14} /> {insights.strategic_action?.time_horizon}
                </div>
                <Badge className="bg-emerald-500 hover:bg-emerald-600 border-none">
                  {insights.strategic_action?.owner}
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};
