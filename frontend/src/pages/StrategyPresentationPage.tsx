import React, { useState } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

// Data from the historical simulations
const allocationData = [
  { name: 'US Economy', GDP: 30.7, Sharpe: 60.0, Safe: 30.0 },
  { name: 'Canadian Economy', GDP: 27.4, Sharpe: 6.7, Safe: 60.0 },
  { name: 'European Economy', GDP: 17.6, Sharpe: 5.0, Safe: 5.0 },
  { name: 'Emerging Markets', GDP: 24.2, Sharpe: 28.3, Safe: 5.0 },
];

const probabilityData = [
  { horizon: '2 Years', 'Macro (GDP)': 76.2, 'Math (Sharpe)': 77.7, 'Safe (MinVol)': 80.1 },
  { horizon: '5 Years', 'Macro (GDP)': 87.1, 'Math (Sharpe)': 87.9, 'Safe (MinVol)': 88.4 },
  { horizon: '10 Years', 'Macro (GDP)': 96.5, 'Math (Sharpe)': 95.8, 'Safe (MinVol)': 97.8 },
  { horizon: '15 Years', 'Macro (GDP)': 99.6, 'Math (Sharpe)': 99.2, 'Safe (MinVol)': 99.6 },
];

const thresholdDataDCA = [
  { horizon: '2 Years', '> 0%': 77.7, '> 5%': 67.9, '> 7%': 63.5, '> 10%': 54.9 },
  { horizon: '5 Years', '> 0%': 87.9, '> 5%': 71.5, '> 7%': 61.0, '> 10%': 41.4 },
  { horizon: '10 Years', '> 0%': 95.8, '> 5%': 78.5, '> 7%': 47.8, '> 10%': 13.1 },
  { horizon: '15 Years', '> 0%': 99.2, '> 5%': 86.9, '> 7%': 45.2, '> 10%': 4.0 },
  { horizon: '25 Years', '> 0%': 100.0, '> 5%': 97.7, '> 7%': 33.3, '> 10%': 0.0 }
];

const thresholdDataLumpSum = [
  { horizon: '2 Years', '> 0%': 78.2, '> 5%': 65.2, '> 7%': 58.3, '> 10%': 49.0 },
  { horizon: '5 Years', '> 0%': 90.6, '> 5%': 67.5, '> 7%': 52.4, '> 10%': 35.2 },
  { horizon: '10 Years', '> 0%': 98.4, '> 5%': 79.5, '> 7%': 49.4, '> 10%': 10.6 },
  { horizon: '15 Years', '> 0%': 100.0, '> 5%': 76.2, '> 7%': 42.9, '> 10%': 6.3 },
  { horizon: '25 Years', '> 0%': 100.0, '> 5%': 99.2, '> 7%': 39.4, '> 10%': 0.0 }
];

const severityData = {
  '15 Years': [
    { name: 'Macro (GDP)', Upside: 6.55, Downside: -0.48 },
    { name: 'Math (Sharpe)', Upside: 6.92, Downside: -0.84 },
    { name: 'Safe (MinVol)', Upside: 6.05, Downside: -0.30 },
  ],
  '5 Years': [
    { name: 'Macro (GDP)', Upside: 9.29, Downside: -5.06 },
    { name: 'Math (Sharpe)', Upside: 9.72, Downside: -5.65 },
    { name: 'Safe (MinVol)', Upside: 9.03, Downside: -4.94 },
  ]
};

const histData = {
  "2 Years": [
    { "bin": "-30% to -28%", "value": 0.0 }, { "bin": "-28% to -26%", "value": 0.0 }, { "bin": "-26% to -24%", "value": 0.3 }, { "bin": "-24% to -22%", "value": 0.5 }, { "bin": "-22% to -20%", "value": 0.8 }, { "bin": "-20% to -18%", "value": 0.3 }, { "bin": "-18% to -16%", "value": 1.3 }, { "bin": "-16% to -14%", "value": 0.5 }, { "bin": "-14% to -12%", "value": 1.5 }, { "bin": "-12% to -10%", "value": 1.5 }, { "bin": "-10% to -8%", "value": 3.0 }, { "bin": "-8% to -6%", "value": 1.8 }, { "bin": "-6% to -4%", "value": 4.0 }, { "bin": "-4% to -2%", "value": 3.3 }, { "bin": "-2% to 0%", "value": 3.8 }, { "bin": "0% to 2%", "value": 5.5 }, { "bin": "2% to 4%", "value": 3.5 }, { "bin": "4% to 6%", "value": 8.0 }, { "bin": "6% to 8%", "value": 6.3 }, { "bin": "8% to 10%", "value": 6.5 }, { "bin": "10% to 12%", "value": 5.3 }, { "bin": "12% to 14%", "value": 6.5 }, { "bin": "14% to 16%", "value": 6.8 }, { "bin": "16% to 18%", "value": 9.8 }, { "bin": "18% to 20%", "value": 5.3 }, { "bin": "20% to 22%", "value": 6.3 }, { "bin": "22% to 24%", "value": 3.0 }, { "bin": "24% to 26%", "value": 2.5 }, { "bin": "26% to 28%", "value": 2.5 }, { "bin": "28% to 30%", "value": 0.0 }
  ],
  "5 Years": [
    { "bin": "-30% to -28%", "value": 0.0 }, { "bin": "-28% to -26%", "value": 0.0 }, { "bin": "-26% to -24%", "value": 0.0 }, { "bin": "-24% to -22%", "value": 0.0 }, { "bin": "-22% to -20%", "value": 0.0 }, { "bin": "-20% to -18%", "value": 0.0 }, { "bin": "-18% to -16%", "value": 0.0 }, { "bin": "-16% to -14%", "value": 0.0 }, { "bin": "-14% to -12%", "value": 0.0 }, { "bin": "-12% to -10%", "value": 0.0 }, { "bin": "-10% to -8%", "value": 0.0 }, { "bin": "-8% to -6%", "value": 0.5 }, { "bin": "-6% to -4%", "value": 0.8 }, { "bin": "-4% to -2%", "value": 2.7 }, { "bin": "-2% to 0%", "value": 5.4 }, { "bin": "0% to 2%", "value": 8.1 }, { "bin": "2% to 4%", "value": 8.6 }, { "bin": "4% to 6%", "value": 12.1 }, { "bin": "6% to 8%", "value": 16.1 }, { "bin": "8% to 10%", "value": 10.5 }, { "bin": "10% to 12%", "value": 9.9 }, { "bin": "12% to 14%", "value": 8.3 }, { "bin": "14% to 16%", "value": 10.2 }, { "bin": "16% to 18%", "value": 4.8 }, { "bin": "18% to 20%", "value": 1.3 }, { "bin": "20% to 22%", "value": 0.5 }, { "bin": "22% to 24%", "value": 0.0 }, { "bin": "24% to 26%", "value": 0.0 }, { "bin": "26% to 28%", "value": 0.0 }, { "bin": "28% to 30%", "value": 0.0 }
  ],
  "10 Years": [
    { "bin": "-30% to -28%", "value": 0.0 }, { "bin": "-28% to -26%", "value": 0.0 }, { "bin": "-26% to -24%", "value": 0.0 }, { "bin": "-24% to -22%", "value": 0.0 }, { "bin": "-22% to -20%", "value": 0.0 }, { "bin": "-20% to -18%", "value": 0.0 }, { "bin": "-18% to -16%", "value": 0.0 }, { "bin": "-16% to -14%", "value": 0.0 }, { "bin": "-14% to -12%", "value": 0.0 }, { "bin": "-12% to -10%", "value": 0.0 }, { "bin": "-10% to -8%", "value": 0.0 }, { "bin": "-8% to -6%", "value": 0.0 }, { "bin": "-6% to -4%", "value": 0.0 }, { "bin": "-4% to -2%", "value": 0.0 }, { "bin": "-2% to 0%", "value": 1.6 }, { "bin": "0% to 2%", "value": 1.6 }, { "bin": "2% to 4%", "value": 10.3 }, { "bin": "4% to 6%", "value": 20.8 }, { "bin": "6% to 8%", "value": 42.6 }, { "bin": "8% to 10%", "value": 12.5 }, { "bin": "10% to 12%", "value": 5.8 }, { "bin": "12% to 14%", "value": 3.8 }, { "bin": "14% to 16%", "value": 1.0 }, { "bin": "16% to 18%", "value": 0.0 }, { "bin": "18% to 20%", "value": 0.0 }, { "bin": "20% to 22%", "value": 0.0 }, { "bin": "22% to 24%", "value": 0.0 }, { "bin": "24% to 26%", "value": 0.0 }, { "bin": "26% to 28%", "value": 0.0 }, { "bin": "28% to 30%", "value": 0.0 }
  ],
  "25 Years": [
    { "bin": "-30% to -28%", "value": 0.0 }, { "bin": "-28% to -26%", "value": 0.0 }, { "bin": "-26% to -24%", "value": 0.0 }, { "bin": "-24% to -22%", "value": 0.0 }, { "bin": "-22% to -20%", "value": 0.0 }, { "bin": "-20% to -18%", "value": 0.0 }, { "bin": "-18% to -16%", "value": 0.0 }, { "bin": "-16% to -14%", "value": 0.0 }, { "bin": "-14% to -12%", "value": 0.0 }, { "bin": "-12% to -10%", "value": 0.0 }, { "bin": "-10% to -8%", "value": 0.0 }, { "bin": "-8% to -6%", "value": 0.0 }, { "bin": "-6% to -4%", "value": 0.0 }, { "bin": "-4% to -2%", "value": 0.0 }, { "bin": "-2% to 0%", "value": 0.0 }, { "bin": "0% to 2%", "value": 0.0 }, { "bin": "2% to 4%", "value": 0.0 }, { "bin": "4% to 6%", "value": 26.5 }, { "bin": "6% to 8%", "value": 71.2 }, { "bin": "8% to 10%", "value": 2.3 }, { "bin": "10% to 12%", "value": 0.0 }, { "bin": "12% to 14%", "value": 0.0 }, { "bin": "14% to 16%", "value": 0.0 }, { "bin": "16% to 18%", "value": 0.0 }, { "bin": "18% to 20%", "value": 0.0 }, { "bin": "20% to 22%", "value": 0.0 }, { "bin": "22% to 24%", "value": 0.0 }, { "bin": "24% to 26%", "value": 0.0 }, { "bin": "26% to 28%", "value": 0.0 }, { "bin": "28% to 30%", "value": 0.0 }
  ]
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-3 border rounded shadow-sm text-sm">
        <p className="font-semibold mb-2">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} style={{ color: entry.color }}>
            {entry.name}: {entry.value}%
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function StrategyPresentationPage() {
  const [severityHorizon, setSeverityHorizon] = useState<'5 Years' | '15 Years'>('15 Years');
  const [thresholdMode, setThresholdMode] = useState<'DCA' | 'Lump Sum'>('DCA');
  const [histHorizon, setHistHorizon] = useState<'2 Years' | '5 Years' | '10 Years' | '25 Years'>('2 Years');

  return (
    <div className="max-w-6xl mx-auto p-6 pb-24 space-y-12">
      
      {/* Header */}
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">The 15-Year Oven Plan</h1>
        <p className="text-xl text-slate-600 max-w-3xl mx-auto">
          A plain-English guide to understanding your portfolio strategy. How do we turn the unpredictable stock market into a reliable funding source for your life?
        </p>
      </div>

      {/* Section 1: The Three Philosophies */}
      <section className="bg-white rounded-xl shadow-sm border p-8 space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-800 border-b pb-2 mb-4">1. The Three Approaches</h2>
          <p className="text-slate-600 mb-6">
            When we build a portfolio, we have to decide where to put the money. We tested three different philosophies using 36 years of historical market data (including the Dot-Com bust and the 2008 Financial Crisis).
          </p>
          <div className="grid md:grid-cols-3 gap-6 mb-8">
            <div className="p-5 bg-blue-50 rounded-lg border border-blue-100">
              <h3 className="font-bold text-blue-900 text-lg mb-2">The "Macro" Approach (GDP)</h3>
              <p className="text-sm text-blue-800">
                <strong>Logic:</strong> Invest where things are actually made.<br/>
                We split the money based on the size of the real-world economies. It's balanced and ignores market "hype."
              </p>
            </div>
            <div className="p-5 bg-emerald-50 rounded-lg border border-emerald-100">
              <h3 className="font-bold text-emerald-900 text-lg mb-2">The "Math" Approach (Sharpe)</h3>
              <p className="text-sm text-emerald-800">
                <strong>Logic:</strong> Maximize the profit engine.<br/>
                A computer looks at the last 20 years and finds the exact mix that generated the most money for the least risk. It heavily favors the US.
              </p>
            </div>
            <div className="p-5 bg-slate-50 rounded-lg border border-slate-200">
              <h3 className="font-bold text-slate-900 text-lg mb-2">The "Safe" Approach (MinVol)</h3>
              <p className="text-sm text-slate-700">
                <strong>Logic:</strong> Avoid the bumps.<br/>
                A mathematically defensive mix. It heavily favors Canada because the Canadian market historically jumps around less than the US market.
              </p>
            </div>
          </div>
        </div>

        <div className="h-[400px]">
          <h4 className="text-center font-semibold text-slate-700 mb-4">Where does the money actually go?</h4>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={allocationData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{fill: '#64748b'}} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={(val) => `${val}%`} tick={{fill: '#64748b'}} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Bar dataKey="GDP" name="Macro (GDP)" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Sharpe" name="Math (Max Sharpe)" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Safe" name="Safe (Min Vol)" fill="#94a3b8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Section 2: Time solves everything */}
      <section className="bg-white rounded-xl shadow-sm border p-8 space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-800 border-b pb-2 mb-4">2. The Magic of Time (Will I lose money?)</h2>
          <p className="text-slate-600 mb-6">
            If you put your money under a mattress, you have a 100% chance of keeping it. If you put it in the stock market, you take a risk. But <strong>time is the antidote to risk</strong>. The chart below shows the historical probability that your regular bi-weekly savings grew <em>instead of shrank</em>.
          </p>
        </div>

        <div className="h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={probabilityData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="horizon" tick={{fill: '#64748b'}} tickLine={false} axisLine={false} />
              <YAxis domain={[0, 100]} tickFormatter={(val) => `${val}%`} tick={{fill: '#64748b'}} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Bar dataKey="Macro (GDP)" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Math (Sharpe)" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Safe (MinVol)" fill="#94a3b8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-amber-50 border-l-4 border-amber-500 p-5 rounded-r">
          <h4 className="font-bold text-amber-900 mb-1">The 15-Year Takeaway</h4>
          <p className="text-amber-800 text-sm">
            At 2 years, investing is a coin flip (~75% chance of success). But because your goal (the oven) is 15 years away, your chance of success jumps to <strong>over 99%</strong> across all strategies. Because you have time, you don't actually need to pick the "Safest" strategy to be safe.
          </p>
        </div>
      </section>

      {/* NEW SECTION: Time Horizon Impact on Thresholds */}
      <section className="bg-white rounded-xl shadow-sm border p-8 space-y-6">
        <div className="flex flex-col md:flex-row md:items-start justify-between mb-4">
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-slate-800 border-b pb-2 mb-4">3. Chasing Returns: How Likely is a Big Win?</h2>
            <p className="text-slate-600 mb-6">
              We just saw that avoiding a loss is highly probable over time. But what about hitting specific targets like 5%, 7%, or even 10%? The chart below illustrates how your investment horizon impacts your chances of hitting these specific return thresholds using the <strong>Math (Sharpe)</strong> portfolio.
            </p>
          </div>
          <div className="md:ml-6 mt-4 md:mt-0">
            <div className="inline-flex bg-slate-100 rounded-lg p-1">
              <button 
                onClick={() => setThresholdMode('DCA')}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${thresholdMode === 'DCA' ? 'bg-white shadow text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
              >
                Monthly Savings (DCA)
              </button>
              <button 
                onClick={() => setThresholdMode('Lump Sum')}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${thresholdMode === 'Lump Sum' ? 'bg-white shadow text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
              >
                Lump Sum
              </button>
            </div>
          </div>
        </div>

        <div className="h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={thresholdMode === 'DCA' ? thresholdDataDCA : thresholdDataLumpSum} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="horizon" tick={{fill: '#64748b'}} tickLine={false} axisLine={false} />
              <YAxis domain={[0, 100]} tickFormatter={(val) => `${val}%`} tick={{fill: '#64748b'}} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Line type="monotone" dataKey="> 0%" stroke="#10b981" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} name="> 0% (Break Even)" />
              <Line type="monotone" dataKey="> 5%" stroke="#3b82f6" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} name="> 5% Return" />
              <Line type="monotone" dataKey="> 7%" stroke="#f59e0b" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} name="> 7% Return" />
              <Line type="monotone" dataKey="> 10%" stroke="#ef4444" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} name="> 10% Return" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-indigo-50 border-l-4 border-indigo-500 p-5 rounded-r">
          <h4 className="font-bold text-indigo-900 mb-1">The Regression to the Mean</h4>
          <p className="text-indigo-800 text-sm">
            Notice how the lines cross. In the short term (2 years), the market is wild—you actually have an over 50% chance of making over 10% a year! But over 25 years, the wild swings average out. The chance of losing money hits 0%, but the chance of making a massive 10% annual return also drops near 0%. Over 15 years, you have a solid 86.9% chance (DCA) to beat a 5% GIC.
          </p>
        </div>
      </section>

      {/* NEW SECTION: Histogram and Kurtosis */}
      <section className="bg-white rounded-xl shadow-sm border p-8 space-y-6">
        <div className="flex flex-col md:flex-row md:items-start justify-between mb-4">
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-slate-800 border-b pb-2 mb-4">4. Kurtosis: The Disappearing Tails</h2>
            <p className="text-slate-600 mb-6">
              You correctly pointed out that the probability of a massive 10% return over 25 years drops to zero for a lump sum. This is not a glitch—it's a statistical phenomenon called <strong>kurtosis flattening</strong>. In the short term, returns are wildly spread out (fat tails). As time goes on, the compounding math "pulls" the extremes into the center. The chart below shows the actual distribution of returns for a Lump Sum in the <strong>Math (Sharpe)</strong> portfolio across all historical periods.
            </p>
          </div>
          <div className="md:ml-6 mt-4 md:mt-0">
            <div className="inline-flex bg-slate-100 rounded-lg p-1">
              {['2 Years', '5 Years', '10 Years', '25 Years'].map(h => (
                <button 
                  key={h}
                  onClick={() => setHistHorizon(h as any)}
                  className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${histHorizon === h ? 'bg-white shadow text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
                >
                  {h}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="h-[400px]">
          {/* Dynamic Probability Computation */}
          {(() => {
            const data = (histData as any)[histHorizon];
            const probLoss = data.filter((d: any) => parseInt(d.bin.split('%')[0]) < 0).reduce((sum: number, d: any) => sum + d.value, 0);
            const probWin = data.filter((d: any) => parseInt(d.bin.split('%')[0]) >= 0).reduce((sum: number, d: any) => sum + d.value, 0);
            return (
              <div className="flex justify-between items-center mb-4 px-8 text-sm font-medium">
                <div className="text-red-600 bg-red-50 px-3 py-1 rounded-md border border-red-100">
                  Pr(Return &lt; 0%) = {probLoss.toFixed(1)}%
                </div>
                <div className="text-emerald-600 bg-emerald-50 px-3 py-1 rounded-md border border-emerald-100">
                  Pr(Return &ge; 0%) = {probWin.toFixed(1)}%
                </div>
              </div>
            );
          })()}
          <ResponsiveContainer width="100%" height="90%">
            <BarChart data={(histData as any)[histHorizon]} margin={{ top: 20, right: 30, left: 20, bottom: 55 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="bin" tick={{fill: '#64748b', fontSize: 11}} tickLine={false} axisLine={false} angle={-45} textAnchor="end" />
              <YAxis tickFormatter={(val) => `${val}%`} tick={{fill: '#64748b'}} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <ReferenceLine x="0% to 2%" stroke="#cbd5e1" strokeWidth={2} />
              <Bar dataKey="value" name="Frequency (%)" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-purple-50 border-l-4 border-purple-500 p-5 rounded-r">
          <h4 className="font-bold text-purple-900 mb-1">Visualizing the Trap</h4>
          <p className="text-purple-800 text-sm">
            Click through the time horizons. At <strong>2 Years</strong>, the graph is wide and flat—there are large chunks of history where you made +25% or lost -20%. This is the "Casino." By <strong>25 Years</strong>, the graph forms a towering spike right around the 6-8% mark. The "tails" (the extremes) have disappeared. This is why you cannot expect to hit a massive 10% average return over 25 years. The market gravity is simply too strong.
          </p>
        </div>
      </section>

      {/* Section 5: Upside vs Downside */}
      <section className="bg-white rounded-xl shadow-sm border p-8 space-y-6">
        <div className="flex flex-col md:flex-row md:items-start justify-between mb-4">
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-slate-800 border-b pb-2 mb-4">5. The Cost of Failure (Upside vs. Downside)</h2>
            <p className="text-slate-600 mb-4">
              Since all strategies are ~99% safe over 15 years, how do we choose? We look at the magnitude of the win vs. the severity of the loss.
            </p>
          </div>
          <div className="md:ml-6 mt-4 md:mt-0">
            <div className="inline-flex bg-slate-100 rounded-lg p-1">
              <button 
                onClick={() => setSeverityHorizon('5 Years')}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${severityHorizon === '5 Years' ? 'bg-white shadow text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
              >
                5 Years
              </button>
              <button 
                onClick={() => setSeverityHorizon('15 Years')}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${severityHorizon === '15 Years' ? 'bg-white shadow text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
              >
                15 Years
              </button>
            </div>
          </div>
        </div>

        <div className="h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={severityData[severityHorizon]} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{fill: '#64748b'}} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={(val) => `${val}%`} tick={{fill: '#64748b'}} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <ReferenceLine y={0} stroke="#cbd5e1" strokeWidth={2} />
              <Bar dataKey="Upside" name="Expected Bonus (When you Win)" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Downside" name="Expected Shortfall (When you Lose)" fill="#ef4444" radius={[0, 0, 4, 4]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-slate-50 p-5 rounded-lg border text-sm text-slate-700 space-y-3">
          <p>
            <strong>The "Upside" (Green):</strong> This is the extra bonus cash you get to pocket when the strategy works. The <strong>Math (Sharpe)</strong> strategy consistently provides the biggest bonus.
          </p>
          <p>
            <strong>The "Downside" (Red):</strong> This is the average loss in the rare case that the 15-year period is negative. In the worst case for the Math strategy, the average shortfall is only -0.84%. For a $5,000 oven, that means you'd be short by less than $200.
          </p>
        </div>
      </section>

      {/* Conclusion */}
      <section className="bg-slate-900 rounded-xl shadow-lg border p-8 text-white space-y-4">
        <h2 className="text-2xl font-bold border-b border-slate-700 pb-2">The Final Conclusion</h2>
        <p className="text-slate-300">
          Because your strategy involves <strong>saving the full principal amount</strong> anyway (the "Principal-Floor"), you don't actually need to worry about the red downside bars. A 0.8% shortfall is negligible.
        </p>
        <p className="text-slate-300">
          Therefore, our recommendation is to use the <strong>Math (Max Sharpe)</strong> approach. Since your 15-year time horizon effectively eliminates the risk of total failure, you might as well choose the engine mathematically designed to give you the biggest green upside bar. 
        </p>
      </section>

    </div>
  );
}