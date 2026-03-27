import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { fetchStatementCoverage, TargetCoverage, StatementCoverage as StatementCoverageData } from '../api/client';

const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function groupMonthsByYear(months: string[]): { year: string; count: number }[] {
  const map: Record<string, number> = {};
  for (const m of months) {
    const y = m.slice(0, 4);
    map[y] = (map[y] || 0) + 1;
  }
  return Object.entries(map).map(([year, count]) => ({ year, count }));
}

function missCount(target: TargetCoverage): number {
  return target.months.filter(c => c.status === 'missing').length;
}

function Cell({ cell, month }: { cell: TargetCoverage['months'][number]; month: string }) {
  const [year, m] = month.split('-');
  const label = `${MONTH_ABBR[parseInt(m) - 1]} ${year}`;

  if (cell.status === 'before_start') {
    return <td className="p-0.5"><div className="w-9 h-9 rounded bg-slate-100" title={`${label} — not tracked`} /></td>;
  }

  if (cell.status === 'missing') {
    return (
      <td className="p-0.5">
        <div
          className="w-9 h-9 rounded bg-red-100 border border-red-300 flex items-center justify-center cursor-default"
          title={`${label} — MISSING`}
        >
          <span className="text-red-500 text-[10px] font-bold leading-none">{parseInt(m)}</span>
        </div>
      </td>
    );
  }

  const isOk = cell.status === 'COMPLETED';
  const bg = isOk ? 'bg-emerald-100 border-emerald-300 hover:bg-emerald-200' : 'bg-amber-100 border-amber-300 hover:bg-amber-200';
  const textColor = isOk ? 'text-emerald-700' : 'text-amber-700';

  return (
    <td className="p-0.5">
      <Link to={`/dashboard/statements/${cell.statement_id}`}>
        <div
          className={`w-9 h-9 rounded border flex items-center justify-center ${bg}`}
          title={`${label} — ${cell.status}`}
        >
          <span className={`text-[10px] font-bold leading-none ${textColor}`}>{parseInt(m)}</span>
        </div>
      </Link>
    </td>
  );
}

function TargetLabel({ target }: { target: TargetCoverage }) {
  const isConsolidated = target.target_type === 'INSTITUTION';
  const inner = (
    <div>
      <div className="font-semibold text-slate-700 text-sm leading-tight truncate max-w-[200px]">
        {target.target_name}
      </div>
      <div className="text-xs text-slate-400 mt-0.5">
        {isConsolidated ? 'Multi-product' : 'Single product'}
      </div>
    </div>
  );

  if (isConsolidated) {
    // No product detail page for institution-level targets
    return <div className="px-4 py-2">{inner}</div>;
  }

  return (
    <Link to={`/dashboard/product/${target.target_id}`} className="block px-4 py-2">
      {inner}
    </Link>
  );
}

export const StatementCoverage: React.FC = () => {
  const [data, setData] = useState<StatementCoverageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchStatementCoverage()
      .then(d => setData(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!data || !scrollRef.current) return;
    const today = new Date();
    const currentMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
    const idx = data.all_months.indexOf(currentMonth);
    if (idx >= 0) {
      scrollRef.current.scrollLeft = Math.max(0, (idx - 3) * 40);
    }
  }, [data]);

  if (loading) return <div className="flex justify-center p-20"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;
  if (error || !data) return <div className="p-20 text-center text-red-500">{error || 'No data'}</div>;

  const yearGroups = groupMonthsByYear(data.all_months);
  const today = new Date();
  const currentMonthKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;

  return (
    <div className="space-y-6 max-w-full pb-20">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Statement Coverage</h1>
          <p className="text-sm text-slate-500 mt-1">Month-by-month coverage based on statement date, not upload date.</p>
        </div>
        <div className="flex gap-4 text-xs text-slate-500 items-center">
          <span className="flex items-center gap-1.5"><span className="w-3.5 h-3.5 rounded bg-emerald-100 border border-emerald-300 inline-block" /> Present</span>
          <span className="flex items-center gap-1.5"><span className="w-3.5 h-3.5 rounded bg-amber-100 border border-amber-300 inline-block" /> Incomplete</span>
          <span className="flex items-center gap-1.5"><span className="w-3.5 h-3.5 rounded bg-red-100 border border-red-300 inline-block" /> Missing</span>
          <span className="flex items-center gap-1.5"><span className="w-3.5 h-3.5 rounded bg-slate-100 inline-block" /> Not tracked</span>
        </div>
      </div>

      {/* Coverage summary pills */}
      <div className="flex flex-wrap gap-2">
        {data.targets.map(t => {
          const missing = missCount(t);
          return (
            <div key={`${t.target_type}-${t.target_id}`} className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${missing > 0 ? 'bg-red-50 border-red-200 text-red-700' : 'bg-emerald-50 border-emerald-200 text-emerald-700'}`}>
              {missing > 0 ? <AlertCircle className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
              {t.target_name}
              {missing > 0 && <span className="ml-1 font-bold">{missing} missing</span>}
            </div>
          );
        })}
      </div>

      {/* Grid */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div ref={scrollRef} className="overflow-x-auto">
          <table className="border-collapse text-sm" style={{ minWidth: 'max-content' }}>
            <thead>
              {/* Year row */}
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="sticky left-0 z-10 bg-slate-50 px-4 py-2 text-left text-xs font-semibold text-slate-500 w-56 border-r border-slate-200">
                  Upload Target
                </th>
                <th className="px-2 py-2 text-xs font-medium text-slate-400 w-10 border-r border-slate-100 text-center">
                  Gap
                </th>
                {yearGroups.map(({ year, count }) => (
                  <th
                    key={year}
                    colSpan={count}
                    className="px-2 py-2 text-center text-xs font-bold text-slate-600 border-r border-slate-200"
                  >
                    {year}
                  </th>
                ))}
              </tr>
              {/* Month row */}
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="sticky left-0 z-10 bg-slate-50 px-4 py-1 text-left text-xs text-slate-400 border-r border-slate-200" />
                <th className="px-2 py-1 text-xs text-slate-400 w-10 border-r border-slate-100 text-center" />
                {data.all_months.map(m => {
                  const [, mo] = m.split('-');
                  const isCurrent = m === currentMonthKey;
                  return (
                    <th
                      key={m}
                      className={`p-0.5 text-center ${isCurrent ? 'bg-blue-50' : ''}`}
                      title={m}
                    >
                      <div className={`w-9 text-[9px] font-medium ${isCurrent ? 'text-blue-600' : 'text-slate-400'}`}>
                        {MONTH_ABBR[parseInt(mo) - 1]}
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.targets.map(target => {
                const missing = missCount(target);
                return (
                  <tr key={`${target.target_type}-${target.target_id}`} className="hover:bg-slate-50/50 transition-colors">
                    {/* Target label — sticky */}
                    <td className="sticky left-0 z-10 bg-white border-r border-slate-200 hover:bg-slate-50">
                      <TargetLabel target={target} />
                    </td>
                    {/* Missing count */}
                    <td className="px-2 py-2 text-center border-r border-slate-100">
                      {missing > 0 ? (
                        <span className="text-xs font-bold text-red-500">{missing}</span>
                      ) : (
                        <span className="text-xs text-emerald-500">✓</span>
                      )}
                    </td>
                    {/* Month cells */}
                    {target.months.map((cell, i) => (
                      <Cell key={i} cell={cell} month={data.all_months[i]} />
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
