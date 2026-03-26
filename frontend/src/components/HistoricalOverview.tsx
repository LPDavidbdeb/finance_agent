import React, { useState } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';
import { TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp } from 'lucide-react';
import { AnnualYearData } from '../api/client';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const fmtK = (n: number) => {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `$${(n / 1_000).toFixed(0)}k`;
  return `$${n.toFixed(0)}`;
};

const fmtFull = (n: number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(n);

// ─── Mini Chart ───────────────────────────────────────────────────────────────

interface MiniMetricChartProps {
  title: string;
  dataKey: keyof AnnualYearData;
  data: AnnualYearData[];
  color: string;       // hex or tailwind-compatible color string
  positiveIsGood: boolean;
}

const MiniMetricChart: React.FC<MiniMetricChartProps> = ({
  title, dataKey, data, color, positiveIsGood,
}) => {
  const current = data[data.length - 1]?.[dataKey] as number ?? 0;
  const prev = data[data.length - 2]?.[dataKey] as number ?? null;
  const delta = prev !== null ? (current as number) - (prev as number) : null;
  const isGood = delta !== null ? (positiveIsGood ? delta > 0 : delta < 0) : null;
  const isFlat = delta !== null && delta === 0;

  return (
    <div className="bg-white rounded-xl border border-slate-100 p-4 flex flex-col gap-2">
      {/* Title + delta badge */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{title}</span>
        {delta !== null && !isFlat && (
          <span className={`flex items-center gap-0.5 text-xs font-semibold px-2 py-0.5 rounded-full ${
            isGood ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'
          }`}>
            {isGood
              ? <TrendingUp className="h-3 w-3" />
              : <TrendingDown className="h-3 w-3" />}
            {delta > 0 ? '+' : ''}{fmtK(delta)}
          </span>
        )}
        {isFlat && (
          <span className="flex items-center gap-0.5 text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-50 text-slate-400">
            <Minus className="h-3 w-3" /> flat
          </span>
        )}
      </div>

      {/* Current year value */}
      <div className="text-2xl font-bold text-slate-800 leading-none">{fmtK(current)}</div>

      {/* Mini area chart */}
      <div className="h-[100px] w-full mt-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.25} />
                <stop offset="95%" stopColor={color} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="year"
              tick={{ fontSize: 10, fill: '#94a3b8' }}
              axisLine={false}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis hide domain={['auto', 'auto']} />
            <Tooltip
              formatter={(value: number) => [fmtFull(value), title]}
              labelFormatter={(label) => `${label}`}
              contentStyle={{
                fontSize: 12,
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: '6px 10px',
              }}
            />
            <Area
              type="monotone"
              dataKey={dataKey as string}
              stroke={color}
              strokeWidth={2}
              fill={`url(#grad-${dataKey})`}
              dot={{ r: 3, fill: color, strokeWidth: 0 }}
              activeDot={{ r: 4 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Year range label */}
      {data.length >= 2 && (
        <div className="text-xs text-slate-400 text-right">
          {data[0].year} → {data[data.length - 1].year}
        </div>
      )}
    </div>
  );
};

// ─── Main Component ───────────────────────────────────────────────────────────

interface HistoricalOverviewProps {
  years: AnnualYearData[];
}

const METRICS: Array<Omit<MiniMetricChartProps, 'data'>> = [
  { title: 'Revenue',    dataKey: 'revenue',    color: '#10b981', positiveIsGood: true  },
  { title: 'Expenses',   dataKey: 'expenses',   color: '#f97316', positiveIsGood: false },
  { title: 'Net Income', dataKey: 'net_income', color: '#3b82f6', positiveIsGood: true  },
  { title: 'Net Worth',  dataKey: 'net_worth',  color: '#6366f1', positiveIsGood: true  },
];

export const HistoricalOverview: React.FC<HistoricalOverviewProps> = ({ years }) => {
  const [expanded, setExpanded] = useState(() => {
    return localStorage.getItem('historicalOverviewExpanded') !== 'false';
  });

  const toggle = () => {
    const next = !expanded;
    setExpanded(next);
    localStorage.setItem('historicalOverviewExpanded', String(next));
  };

  return (
    <section id="history" className="space-y-3">
      {/* Section header */}
      <div
        className="flex items-center justify-between cursor-pointer select-none group"
        onClick={toggle}
      >
        <div>
          <h2 className="text-sm font-semibold text-slate-700 group-hover:text-slate-900 transition-colors">
            Financial History
          </h2>
          <p className="text-xs text-slate-400">
            {years[0]?.year} – {years[years.length - 1]?.year} · {years.length} years
          </p>
        </div>
        <button className="text-slate-400 hover:text-slate-600 transition-colors">
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {/* 2×2 grid */}
      {expanded && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {METRICS.map((m) => (
            <MiniMetricChart key={m.dataKey as string} {...m} data={years} />
          ))}
        </div>
      )}
    </section>
  );
};
