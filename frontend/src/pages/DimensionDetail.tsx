import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { fetchDimensionDetail } from '../api/client';
import { 
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend
} from 'recharts';
import { ArrowLeft, Loader2, TrendingUp, TrendingDown, PieChart as PieIcon, List, ChevronRight, Calendar } from 'lucide-react';

interface SubcategoryItem {
  name: string;
  balance: number;
  type: 'subcategory';
  merchants: { name: string; balance: number }[];
}

interface MerchantSubItem {
  name: string;
  balance: number;
  type?: undefined;
}

interface LineItem {
  id?: number;
  name: string;
  balance: number;
  sub_items?: (SubcategoryItem | MerchantSubItem)[];
}

interface MerchantItem {
  id: number;
  name: string;
  balance: number;
}

interface DimensionData {
  dimension_name: string;
  total_amount: number;
  line_items: LineItem[];
  merchant_items: MerchantItem[];
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d', '#ffc658', '#8dd1e1'];

export const DimensionDetail: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const [searchParams] = useSearchParams();
  const year = parseInt(searchParams.get('year') || new Date().getFullYear().toString());
  const navigate = useNavigate();

  const [data, setData] = useState<DimensionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  type PeriodMode = 'year' | 'month' | 'bi-weekly' | 'weekly';
  const [periodMode, setPeriodMode] = useState<PeriodMode>('year');
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});
  const [expandedSubs, setExpandedSubs] = useState<Record<string, boolean>>({});

  const toggleSub = (rowIdx: number, subIdx: number) => {
    const key = `${rowIdx}-${subIdx}`;
    setExpandedSubs(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const PERIOD_CONFIG: Record<PeriodMode, { label: string; divisor: number; suffix: string }> = {
    year:       { label: 'Year',   divisor: 1,  suffix: '/ yr'    },
    month:      { label: 'Month',  divisor: 12, suffix: '/ mo'    },
    'bi-weekly':{ label: '2-Week', divisor: 26, suffix: '/ 2-wk'  },
    weekly:     { label: 'Week',   divisor: 52, suffix: '/ wk'    },
  };

  const { divisor, suffix } = PERIOD_CONFIG[periodMode];
  const scale = (v: number) => v / divisor;

  const toggleRow = (idx: number) => {
    setExpandedRows(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  useEffect(() => {
    if (slug) {
      loadData(slug, year);
    }
  }, [slug, year]);

  const loadData = async (dimensionSlug: string, targetYear: number) => {
    try {
      setLoading(true);
      setError(null);
      const result = await fetchDimensionDetail(dimensionSlug, targetYear);
      setData(result);
    } catch (err: any) {
      setError(err.message || "Failed to load report data.");
    } finally {
      setLoading(false);
    }
  };

  const chartData = useMemo(() => {
    if (!data) return [];
    const sorted = [...data.line_items].sort((a, b) => b.balance - a.balance);
    if (sorted.length <= 8) return sorted.map(i => ({ ...i, balance: scale(i.balance) }));
    const top = sorted.slice(0, 7).map(i => ({ ...i, balance: scale(i.balance) }));
    const otherSum = sorted.slice(7).reduce((acc, curr) => acc + scale(curr.balance), 0);
    return [...top, { name: 'Others', balance: otherSum }];
  }, [data, divisor]);

  if (loading) return <div className="flex justify-center p-20"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;
  if (error || !data) return <div className="p-20 text-center text-red-500">{error || "Report not found"}</div>;

  const isPositive = data.total_amount >= 0;

  return (
    <div className="space-y-8 max-w-6xl mx-auto w-full pb-20">
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={() => navigate('/dashboard')} size="sm" className="gap-2">
          <ArrowLeft className="h-4 w-4" /> Back to Dashboard
        </Button>
        <Badge variant="outline" className="px-3 py-1 text-sm font-medium">
          Fiscal Year {year}
        </Badge>
      </div>

      {/* Hero Header */}
      <div className="bg-white p-10 rounded-2xl shadow-sm border border-slate-200 text-center relative overflow-hidden">
        <div className="absolute top-0 right-0 p-4 opacity-5">
          {isPositive ? <TrendingUp size={120} /> : <TrendingDown size={120} />}
        </div>
        <p className="text-sm font-bold uppercase tracking-widest text-slate-400 mb-2">{data.dimension_name}</p>
        <h1 className={`text-6xl font-black tracking-tighter ${isPositive ? 'text-slate-900' : 'text-red-600'}`}>
          ${scale(data.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </h1>
        <p className="text-sm text-slate-400 mt-1">{suffix}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Visualization */}
        <Card className="shadow-sm">
          <CardHeader className="bg-slate-50/50 border-b border-slate-100">
            <CardTitle className="text-lg flex items-center gap-2">
              <PieIcon className="h-5 w-5 text-blue-600" />
              Distribution ({PERIOD_CONFIG[periodMode].label})
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="h-[400px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={80}
                    outerRadius={130}
                    paddingAngle={5}
                    dataKey="balance"
                    nameKey="name"
                  >
                    {chartData.map((_entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: any) => `$${value.toLocaleString()}`} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Line Items Table */}
        <Card className="shadow-sm">
          <CardHeader className="bg-slate-50/50 border-b border-slate-100 flex flex-row items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <List className="h-5 w-5 text-emerald-600" />
              Breakdown
            </CardTitle>
            <div className="flex bg-slate-100 p-1 rounded-md text-[10px]">
              {(Object.keys(PERIOD_CONFIG) as PeriodMode[]).map(mode => (
                <button
                  key={mode}
                  className={`px-2 py-1 rounded flex items-center gap-1 ${periodMode === mode ? 'bg-white shadow-sm font-bold' : 'text-slate-500'}`}
                  onClick={() => setPeriodMode(mode)}
                >
                  {PERIOD_CONFIG[mode].label}
                </button>
              ))}
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50/50 border-b border-slate-100 text-slate-500 font-medium">
                  <tr>
                    <th className="px-6 py-3 text-left">Category</th>
                    <th className="px-6 py-3 text-right">Amount <span className="text-slate-400 font-normal">{suffix}</span></th>
                    <th className="px-6 py-3 text-right">Prop.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.line_items.map((item, idx) => (
                    <React.Fragment key={idx}>
                      <tr className="hover:bg-slate-50/50 transition-colors group">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            {item.sub_items && item.sub_items.length > 0 && (
                              <button
                                onClick={() => toggleRow(idx)}
                                className="p-1 hover:bg-slate-200 rounded transition-colors text-slate-400"
                              >
                                <ChevronRight className={`h-3 w-3 transition-transform ${expandedRows[idx] ? 'rotate-90' : ''}`} />
                              </button>
                            )}
                            {item.id ? (
                              <Link
                                to={`/dashboard/accounts/${item.id}?year=${year}`}
                                className="font-semibold text-slate-700 hover:text-blue-600 flex items-center gap-2"
                              >
                                {item.name}
                              </Link>
                            ) : (
                              <span className="font-semibold text-slate-700">{item.name}</span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 text-right font-mono font-medium">
                          ${scale(item.balance).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-6 py-4 text-right text-slate-400 text-xs">
                          {((item.balance / (data.total_amount || 1)) * 100).toFixed(1)}%
                        </td>
                      </tr>
                      {expandedRows[idx] && item.sub_items && item.sub_items.map((sub, sIdx) => {
                        if (sub.type === 'subcategory') {
                          const subKey = `${idx}-${sIdx}`;
                          const subExpanded = !!expandedSubs[subKey];
                          return (
                            <React.Fragment key={`sub-${idx}-${sIdx}`}>
                              {/* Subcategory header row — clickable accordion */}
                              <tr
                                className="bg-slate-100/60 border-t border-slate-200 cursor-pointer hover:bg-slate-100 transition-colors"
                                onClick={() => toggleSub(idx, sIdx)}
                              >
                                <td className="px-10 py-2 text-slate-600 font-semibold text-xs uppercase tracking-wide">
                                  <div className="flex items-center gap-1.5">
                                    <ChevronRight className={`h-3 w-3 text-slate-400 transition-transform ${subExpanded ? 'rotate-90' : ''}`} />
                                    {sub.name}
                                  </div>
                                </td>
                                <td className="px-6 py-2 text-right text-slate-600 font-mono font-semibold text-xs">
                                  ${scale(sub.balance).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                </td>
                                <td className="px-6 py-2 text-right text-slate-400 text-xs">
                                  {((sub.balance / (data!.total_amount || 1)) * 100).toFixed(1)}%
                                </td>
                              </tr>
                              {/* Merchants — shown only when subcategory is expanded */}
                              {subExpanded && sub.merchants.map((m, mIdx) => (
                                <tr key={`sub-${idx}-${sIdx}-m-${mIdx}`} className="bg-slate-50/30 text-xs italic">
                                  <td className="px-16 py-1.5 text-slate-400">{m.name}</td>
                                  <td className="px-6 py-1.5 text-right text-slate-400 font-mono">
                                    ${scale(m.balance).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                  </td>
                                  <td></td>
                                </tr>
                              ))}
                            </React.Fragment>
                          );
                        }
                        return (
                          <tr key={`sub-${idx}-${sIdx}`} className="bg-slate-50/30 text-xs italic">
                            <td className="px-12 py-2 text-slate-500">{sub.name}</td>
                            <td className="px-6 py-2 text-right text-slate-500 font-mono">
                              ${scale(sub.balance).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </td>
                            <td></td>
                          </tr>
                        );
                      })}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
