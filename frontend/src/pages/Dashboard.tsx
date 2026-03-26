import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import {
  fetchSpendingByCategory,
  fetchAnnualStatements,
  fetchAnnualStatementsHistory,
  fetchDimensionDetail,
  fetchDimensionEvolution,
  fetchAvailableYears,
  AnnualYearData,
} from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  PieChart, Pie, Cell, AreaChart, Area, ReferenceLine,
} from 'recharts';
import { Loader2, TrendingDown, TrendingUp, Wallet, Receipt, PieChart as PieIcon, RefreshCw } from 'lucide-react';
import { DrillDownModal } from '../components/DrillDownModal';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#6366f1'];

type Dimension = 'revenue' | 'expenses' | 'net-income' | 'assets' | 'liabilities' | 'net-worth';

export const Dashboard: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // Global Controls
  const currentYear = new Date().getFullYear();
  const [availableYears, setAvailableYears] = useState<number[]>([currentYear]);
  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [selectedInterval, setSelectedInterval] = useState<'monthly' | 'bi-weekly'>('monthly');
  const [activeDimension, setActiveDimension] = useState<Dimension>('expenses');

  // Data State
  const [evolutionData, setEvolutionData] = useState<any[]>([]);
  const [categoryData, setCategoryData] = useState<any[]>([]);
  const [statements, setStatements] = useState<any>(null);
  const [historicalYears, setHistoricalYears] = useState<AnnualYearData[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Drill-down State
  const [isDrillDownOpen, setIsDrillDownOpen] = useState(false);
  const [drillDownPeriod, setDrillDownPeriod] = useState('');

  // Process data to only show Top 4 + OTHER
  const processedData = useMemo(() => {
    if (evolutionData.length === 0) return [];
    
    // 1. Sum up all keys across the whole period
    const totals: Record<string, number> = {};
    evolutionData.forEach(item => {
      Object.keys(item).forEach(key => {
        if (key !== 'period' && key !== 'amount') {
          totals[key] = (totals[key] || 0) + (item[key] || 0);
        }
      });
    });

    // 2. Sort and pick top 4
    const sortedKeys = Object.entries(totals)
      .sort((a, b) => b[1] - a[1])
      .map(entry => entry[0]);
    
    const top4 = sortedKeys.slice(0, 4);
    const others = sortedKeys.slice(4);

    // 3. Rebuild data
    return evolutionData.map(item => {
      const newItem: any = { period: item.period, amount: item.amount };
      let otherSum = 0;
      
      top4.forEach(key => {
        newItem[key] = item[key] || 0;
      });
      
      others.forEach(key => {
        otherSum += (item[key] || 0);
      });
      
      if (others.length > 0) {
        newItem['OTHER'] = otherSum;
      }
      
      return newItem;
    });
  }, [evolutionData]);

  // Extract unique category keys for stacked chart (sorted by total volume)
  const categoryKeys = useMemo(() => {
    if (processedData.length === 0) return [];
    
    // Sum again on processed data to get consistent sorting
    const totals: Record<string, number> = {};
    processedData.forEach(item => {
      Object.keys(item).forEach(key => {
        if (key !== 'period' && key !== 'amount') {
          totals[key] = (totals[key] || 0) + (item[key] || 0);
        }
      });
    });

    return Object.entries(totals)
      .sort((a, b) => b[1] - a[1])
      .map(entry => entry[0]);
  }, [processedData]);

  // Load available years on mount
  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    const loadYears = async () => {
      try {
        const data = await fetchAvailableYears();
        setAvailableYears(data.available_years);
        if (data.available_years.length > 0) {
          setSelectedYear(data.available_years[0]);
        }
      } catch (err) {
        console.error('Failed to load available years:', err);
        setAvailableYears([currentYear]);
      }
    };

    loadYears();
  }, [isAuthenticated, navigate]);

  // Fetch historical data once after years are known — not re-fetched on tab/year changes
  useEffect(() => {
    if (!isAuthenticated || availableYears.length === 0) return;
    fetchAnnualStatementsHistory()
      .then(data => setHistoricalYears(data.years))
      .catch(() => {}); // non-fatal — panel simply won't render
  }, [isAuthenticated, availableYears.length]);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    loadAllData();
  }, [isAuthenticated, navigate, selectedYear, selectedInterval, activeDimension]);

  const loadAllData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const startDate = `${selectedYear}-01-01`;
      const endDate = `${selectedYear}-12-31`;

      const promises: Promise<any>[] = [
        fetchAnnualStatements(selectedYear),
        fetchDimensionEvolution(activeDimension, startDate, endDate, selectedInterval)
      ];

      if (activeDimension === 'expenses') {
        promises.push(fetchSpendingByCategory(startDate, endDate));
      } else {
        promises.push(fetchDimensionDetail(activeDimension, selectedYear));
      }

      const results = await Promise.all(promises);
      setStatements(results[0]);
      setEvolutionData(results[1]);

      if (activeDimension === 'expenses') {
        setCategoryData(results[2]);
      } else {
        const dimensionDetail = results[2];
        setCategoryData(dimensionDetail.line_items.map((item: any) => ({
          id: item.id,
          category: item.name,
          amount: Math.abs(item.balance)
        })));
      }

    } catch (err: any) {
      if (err.message === "Unauthorized") {
         navigate('/login');
      } else {
         setError(err.message || 'Failed to load dashboard data.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleBarClick = (data: any) => {
    if (data && data.period) {
      setDrillDownPeriod(data.period);
      setIsDrillDownOpen(true);
    }
  };

  const handlePieClick = (data: any) => {
    if (data && data.id) {
      navigate(`/dashboard/accounts/${data.id}?year=${selectedYear}`);
    }
  };

  const truncateLabel = (label: string, maxLength: number = 25) => {
    if (!label) return '';
    if (label.length <= maxLength) return label;
    return label.substring(0, maxLength) + '...';
  };

  const dimensionConfig = useMemo(() => ({
    revenue: { color: 'border-l-green-500', icon: TrendingUp, label: 'Revenue', iconColor: 'text-green-500' },
    expenses: { color: 'border-l-orange-500', icon: TrendingDown, label: 'Expenses', iconColor: 'text-orange-500' },
    'net-income': { color: 'border-l-blue-500', icon: TrendingUp, label: 'Net Income', iconColor: 'text-blue-500' },
    assets: { color: 'border-l-emerald-600', icon: Wallet, label: 'Total Assets', iconColor: 'text-emerald-600' },
    liabilities: { color: 'border-l-red-500', icon: Receipt, label: 'Liabilities', iconColor: 'text-red-600' },
    'net-worth': { color: 'bg-slate-900 text-white', icon: Wallet, label: 'Net Worth', iconColor: 'text-blue-400' },
  }), []);

  if (loading && !statements) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
        <p className="text-slate-500 font-medium">Building your command center...</p>
      </div>
    );
  }

  const dimToHistoryKey: Record<Dimension, keyof AnnualYearData> = {
    revenue: 'revenue',
    expenses: 'expenses',
    'net-income': 'net_income',
    assets: 'assets',
    liabilities: 'liabilities',
    'net-worth': 'net_worth',
  };

  const dimToSparkColor: Record<Dimension, string> = {
    revenue: '#10b981',
    expenses: '#f97316',
    'net-income': '#3b82f6',
    assets: '#059669',
    liabilities: '#ef4444',
    'net-worth': '#818cf8',
  };

  const renderSummaryCard = (dim: Dimension, amount: number) => {
    const config = dimensionConfig[dim];
    const isActive = activeDimension === dim;
    const isNetWorth = dim === 'net-worth';
    const sparkColor = dimToSparkColor[dim];
    const histKey = dimToHistoryKey[dim];
    const sparkData = historicalYears.length > 1 ? historicalYears : [];

    return (
      <Card
        key={dim}
        className={`cursor-pointer transition-all duration-200 border-l-4 ${config.color} ${
          isActive
            ? 'shadow-lg ring-2 ring-blue-400 ring-offset-2 scale-[1.02]'
            : 'hover:bg-slate-50 hover:shadow-md'
        } ${isNetWorth && !isActive ? 'bg-slate-900 text-white border-none' : ''} ${isNetWorth && isActive ? 'bg-slate-800 text-white ring-offset-slate-900' : ''}`}
        onClick={() => setActiveDimension(dim)}
      >
        <CardHeader className="pb-1">
          <CardDescription className={`text-[10px] uppercase font-bold tracking-widest ${isNetWorth ? 'text-slate-400' : ''}`}>
            {config.label}
          </CardDescription>
          <CardTitle className="text-xl flex items-center gap-2">
            <config.icon className={`h-4 w-4 ${config.iconColor}`} />
            ${Math.abs(amount).toLocaleString()}
          </CardTitle>
        </CardHeader>

        {sparkData.length > 1 && (
          <div className="h-[52px] w-full px-1 pb-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparkData} margin={{ top: 2, right: 4, bottom: 0, left: 4 }}>
                <defs>
                  <linearGradient id={`spark-${dim}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={sparkColor} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={sparkColor} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="year" hide />
                <YAxis hide domain={['auto', 'auto']} />
                <Tooltip
                  formatter={(v: any) => [`$${Math.abs(v as number).toLocaleString()}`, config.label]}
                  labelFormatter={(l) => `${l}`}
                  contentStyle={{ fontSize: 11, borderRadius: 6, padding: '4px 8px' }}
                />
                <Area
                  type="monotone"
                  dataKey={histKey as string}
                  stroke={sparkColor}
                  strokeWidth={1.5}
                  fill={`url(#spark-${dim})`}
                  dot={false}
                  isAnimationActive={false}
                />
                <ReferenceLine
                  x={selectedYear}
                  stroke={isNetWorth ? '#94a3b8' : '#64748b'}
                  strokeWidth={1.5}
                  strokeDasharray="3 3"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    );
  };

  return (
    <div className="space-y-8 pb-12">
      {/* Sticky Dashboard Header */}
      <div className="sticky top-0 z-30 space-y-4 bg-gray-50/95 backdrop-blur-sm py-4">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-4 rounded-xl shadow-sm border border-slate-200">
          <div>
            <h1 className="text-2xl font-black tracking-tight text-slate-900 uppercase">Command Center</h1>
            <p className="text-xs font-bold text-slate-400 uppercase tracking-tighter">Real-time Financial Oversight</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex bg-slate-100 p-1 rounded-lg">
              <button 
                className={`px-3 py-1 text-xs rounded-md transition-all ${selectedInterval === 'monthly' ? 'bg-white shadow-sm font-bold text-blue-600' : 'text-slate-500 hover:text-slate-700'}`}
                onClick={() => setSelectedInterval('monthly')}
              >
                Monthly
              </button>
              <button 
                className={`px-3 py-1 text-xs rounded-md transition-all ${selectedInterval === 'bi-weekly' ? 'bg-white shadow-sm font-bold text-blue-600' : 'text-slate-500 hover:text-slate-700'}`}
                onClick={() => setSelectedInterval('bi-weekly')}
              >
                Bi-Weekly
              </button>
            </div>
            <select 
              value={selectedYear}
              onChange={(e) => setSelectedYear(parseInt(e.target.value))}
              className="bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-sm font-black text-slate-700 focus:ring-2 focus:ring-blue-500 outline-none cursor-pointer"
            >
              {availableYears.map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <Button onClick={loadAllData} variant="ghost" size="icon" className="h-9 w-9 rounded-lg text-slate-400 hover:text-blue-600">
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* Annual Summary Cards as Tabs */}
        {statements && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {renderSummaryCard('revenue', statements.income_statement.revenue)}
            {renderSummaryCard('expenses', statements.income_statement.expenses)}
            {renderSummaryCard('net-income', statements.income_statement.net_income)}
            {renderSummaryCard('assets', statements.balance_sheet.assets)}
            {renderSummaryCard('liabilities', statements.balance_sheet.liabilities)}
            {renderSummaryCard('net-worth', statements.balance_sheet.net_worth)}
          </div>
        )}
      </div>

      {error && (
        <Card className="bg-red-50 border-red-200">
          <CardContent className="pt-6">
            <p className="text-red-600 font-medium text-center">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Dynamic Chart Zone */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Detail Chart */}
        <Card className="shadow-sm border-slate-200 overflow-hidden">
          <CardHeader className="bg-slate-50/50 border-b border-slate-100">
            <div className="flex justify-between items-center">
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-blue-600" />
                  {activeDimension.replace('-', ' ').toUpperCase()} Trend
                </CardTitle>
                <CardDescription>Chronological performance oversight</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => navigate(`/dashboard/dimension/${activeDimension}?year=${selectedYear}`)}>
                Full Report
              </Button>
            </div>
          </CardHeader>
          <CardContent className="pt-6">
            {processedData.length > 0 ? (
              <div className="h-[350px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={processedData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis 
                      dataKey="period" 
                      axisLine={false} 
                      tickLine={false} 
                      tick={false} // Clean up bottom of chart
                    />
                    <YAxis 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{fontSize: 10, fill: '#64748b', fontWeight: 600}} 
                      tickFormatter={(v) => `$${v.toLocaleString()}`} 
                    />
                    <Tooltip 
                      cursor={{fill: '#f1f5f9', opacity: 0.4}} 
                      contentStyle={{
                        borderRadius: '12px', 
                        border: '1px solid #e2e8f0', 
                        boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
                        padding: '12px'
                      }} 
                      itemSorter={(item: any) => -item.value} // Sort tooltip by largest amount first
                      formatter={(value: any, name: any) => [`$${value.toLocaleString()}`, name]}
                    />
                    {categoryKeys.map((key, index) => (
                      <Bar 
                        key={key}
                        dataKey={key} 
                        stackId="a"
                        fill={COLORS[index % COLORS.length]} 
                        radius={index === categoryKeys.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
                        onClick={handleBarClick}
                        className="cursor-pointer hover:opacity-80 transition-opacity"
                      />
                    ))
                    }
                    {/* Fallback if no breakdown available (e.g. Net Income) */}
                    {categoryKeys.length === 0 && (
                      <Bar 
                        dataKey="amount" 
                        fill="#3b82f6" 
                        radius={[4, 4, 0, 0]} 
                        onClick={handleBarClick}
                        className="cursor-pointer hover:opacity-80 transition-opacity"
                      />
                    )}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-[350px] flex items-center justify-center text-slate-400 italic text-sm text-center px-8">
                Trend data for this dimension is currently available in the Full Report.<br/>Select Expenses or Revenue for interactive bar drill-down.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Composition Chart */}
        <Card className="shadow-sm border-slate-200 overflow-hidden">
          <CardHeader className="bg-slate-50/50 border-b border-slate-100">
            <CardTitle className="text-lg flex items-center gap-2">
              <PieIcon className="h-5 w-5 text-blue-500" />
              {activeDimension.replace('-', ' ').toUpperCase()} Composition
            </CardTitle>
            <CardDescription>Allocation across sub-categories</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="h-[350px] w-full flex items-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={categoryData}
                    cx="50%"
                    cy="50%"
                    innerRadius={80}
                    outerRadius={120}
                    paddingAngle={5}
                    dataKey="amount"
                    nameKey="category"
                    onClick={handlePieClick}
                    className="cursor-pointer"
                  >
                    {categoryData.map((_entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: any) => `$${value.toLocaleString()}`} />
                  <Legend 
                    layout="vertical" 
                    align="right" 
                    verticalAlign="middle" 
                    iconType="circle"
                    width={200}
                    formatter={(value) => (
                      <span className="text-[10px] text-slate-600 font-bold uppercase" title={value}>
                        {truncateLabel(value)}
                      </span>
                    )}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <DrillDownModal 
        isOpen={isDrillDownOpen}
        onClose={() => setIsDrillDownOpen(false)}
        dimension={activeDimension}
        period={drillDownPeriod}
      />
    </div>
  );
};
