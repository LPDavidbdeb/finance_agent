import React, { useState, useCallback, useEffect } from 'react';
import { Plus, Trash2, ChevronDown, ChevronUp, TrendingDown, TrendingUp, Calculator, CheckCircle2, BookMarked, X } from 'lucide-react';
import {
  simulateScenarios, commitSchedule, fetchSchedules, fetchSchedule, deleteSchedule,
  ScenarioSpec, ScenarioResult, PeriodRow, AnnuityScheduleOut, AnnuityScheduleListOut,
} from '../api/client';

// ─── Types ────────────────────────────────────────────────────────────────────

type FrequencyOption = 'MONTHLY' | 'BIWEEKLY' | 'WEEKLY' | 'ANNUALLY';

interface ScenarioForm {
  id: string;
  name: string;
  type: 'LOAN_AMORTIZATION' | 'SINKING_FUND';
  principal: string;
  annual_rate: string;
  amortization_years: string;
  payment_frequency: FrequencyOption;
  start_date: string;
  current_balance: string;
}

const generateScenarioId = (): string => {
  const cryptoObj = globalThis.crypto;
  if (cryptoObj?.randomUUID) {
    return cryptoObj.randomUUID();
  }

  if (cryptoObj?.getRandomValues) {
    const bytes = new Uint8Array(16);
    cryptoObj.getRandomValues(bytes);

    // RFC4122 v4 bit masks for compatibility with systems expecting UUID shape.
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;

    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}`;
  }

  return `scenario-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
};

const defaultForm = (): ScenarioForm => ({
  id: generateScenarioId(),
  name: '',
  type: 'LOAN_AMORTIZATION',
  principal: '',
  annual_rate: '',
  amortization_years: '25',
  payment_frequency: 'MONTHLY',
  start_date: new Date().toISOString().slice(0, 10),
  current_balance: '0',
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

const fmt = (n: number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 2 }).format(n);

const fmtShort = (n: number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(n);

const FREQ_LABELS: Record<FrequencyOption, string> = {
  MONTHLY: 'Monthly',
  BIWEEKLY: 'Bi-weekly',
  WEEKLY: 'Weekly',
  ANNUALLY: 'Annual',
};

// ─── Schedule Table ───────────────────────────────────────────────────────────

const ScheduleTable: React.FC<{ schedule: PeriodRow[]; type: 'LOAN_AMORTIZATION' | 'SINKING_FUND' }> = ({ schedule, type }) => {
  const [showAll, setShowAll] = useState(false);
  const rows = showAll ? schedule : schedule.slice(0, 12);

  return (
    <div className="mt-3">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-slate-500 border-b border-slate-100">
            <th className="text-left py-1 font-medium">#</th>
            <th className="text-left py-1 font-medium">Date</th>
            <th className="text-right py-1 font-medium">Payment</th>
            <th className="text-right py-1 font-medium">{type === 'LOAN_AMORTIZATION' ? 'Interest' : 'Earned'}</th>
            <th className="text-right py-1 font-medium">{type === 'LOAN_AMORTIZATION' ? 'Principal' : 'Contrib.'}</th>
            <th className="text-right py-1 font-medium">Balance</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.period_number} className="border-b border-slate-50 hover:bg-slate-50">
              <td className="py-1 text-slate-400">{row.period_number}</td>
              <td className="py-1 text-slate-600">{row.payment_date}</td>
              <td className="py-1 text-right font-mono">{fmtShort(row.payment_amount)}</td>
              <td className="py-1 text-right font-mono text-orange-600">{fmtShort(row.interest_portion)}</td>
              <td className="py-1 text-right font-mono text-blue-600">{fmtShort(row.principal_portion)}</td>
              <td className="py-1 text-right font-mono text-slate-700">{fmtShort(row.balance_after)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {schedule.length > 12 && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="mt-2 text-xs text-blue-600 hover:underline flex items-center gap-1"
        >
          {showAll ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          {showAll ? 'Show less' : `Show all ${schedule.length} periods`}
        </button>
      )}
    </div>
  );
};

// ─── Result Card ──────────────────────────────────────────────────────────────

const ResultCard: React.FC<{
  result: ScenarioResult;
  spec: ScenarioSpec;
  isBaseline: boolean;
  index: number;
  onCommitted: () => void;
}> = ({ result, spec, isBaseline, index, onCommitted }) => {
  const [expanded, setExpanded] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [committed, setCommitted] = useState(false);
  const [commitError, setCommitError] = useState<string | null>(null);

  const CARD_COLORS = [
    'border-blue-400 bg-blue-50',
    'border-emerald-400 bg-emerald-50',
    'border-violet-400 bg-violet-50',
    'border-amber-400 bg-amber-50',
    'border-rose-400 bg-rose-50',
  ];
  const colorClass = CARD_COLORS[index % CARD_COLORS.length];
  const deltaPositive = result.delta_vs_baseline !== null && result.delta_vs_baseline > 0;

  const handleCommit = async () => {
    setCommitError(null);
    setCommitting(true);
    try {
      await commitSchedule(spec);
      setCommitted(true);
      onCommitted();
    } catch (e: unknown) {
      setCommitError(e instanceof Error ? e.message : 'Commit failed');
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div className={`rounded-xl border-2 p-4 flex flex-col gap-3 ${colorClass}`}>
      <div className="flex justify-between items-start">
        <div>
          <h3 className="font-semibold text-slate-800">{result.name}</h3>
          <span className="text-xs text-slate-500">
            {result.type === 'LOAN_AMORTIZATION' ? 'Loan / Mortgage' : 'Sinking Fund'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isBaseline && (
            <span className="text-xs bg-blue-600 text-white px-2 py-0.5 rounded-full font-medium">Baseline</span>
          )}
          {committed && (
            <span className="text-xs bg-emerald-600 text-white px-2 py-0.5 rounded-full font-medium flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3" /> Committed
            </span>
          )}
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-white/70 rounded-lg p-3">
          <div className="text-xs text-slate-500 mb-1">Payment / period</div>
          <div className="text-xl font-bold text-slate-800">{fmt(result.payment_amount)}</div>
        </div>
        <div className="bg-white/70 rounded-lg p-3">
          <div className="text-xs text-slate-500 mb-1">FCF impact</div>
          <div className="text-xl font-bold text-red-600">{fmt(result.fcf_impact_monthly)}</div>
        </div>
        <div className="bg-white/70 rounded-lg p-3">
          <div className="text-xs text-slate-500 mb-1">Total interest</div>
          <div className="text-lg font-semibold text-orange-600">{fmt(result.total_interest_paid)}</div>
        </div>
        <div className="bg-white/70 rounded-lg p-3">
          <div className="text-xs text-slate-500 mb-1">Total cost</div>
          <div className="text-lg font-semibold text-slate-700">{fmt(result.total_cost)}</div>
        </div>
      </div>

      {/* Delta vs baseline */}
      {result.delta_vs_baseline !== null && (
        <div className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
          deltaPositive ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'
        }`}>
          {deltaPositive ? <TrendingDown className="h-4 w-4" /> : <TrendingUp className="h-4 w-4" />}
          {deltaPositive
            ? `${fmt(result.delta_vs_baseline)} more per period than baseline`
            : `${fmt(Math.abs(result.delta_vs_baseline))} less per period than baseline`}
        </div>
      )}

      {/* Actions row */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 transition-colors"
        >
          {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          {expanded ? 'Hide' : 'Show'} schedule
        </button>

        {!committed && (
          <button
            onClick={handleCommit}
            disabled={committing}
            className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 disabled:bg-slate-300 text-white rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
          >
            <BookMarked className="h-3.5 w-3.5" />
            {committing ? 'Committing…' : 'Commit'}
          </button>
        )}
      </div>

      {commitError && (
        <div className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">{commitError}</div>
      )}

      {expanded && <ScheduleTable schedule={result.schedule} type={result.type} />}
    </div>
  );
};

// ─── Form Card ────────────────────────────────────────────────────────────────

const FormCard: React.FC<{
  form: ScenarioForm;
  index: number;
  canRemove: boolean;
  onChange: (id: string, field: keyof ScenarioForm, value: string) => void;
  onRemove: (id: string) => void;
}> = ({ form, index, canRemove, onChange, onRemove }) => (
  <div className="border border-slate-200 rounded-xl p-4 bg-white space-y-3">
    <div className="flex justify-between items-center">
      <span className="text-sm font-medium text-slate-600">Scenario {index + 1}</span>
      {canRemove && (
        <button onClick={() => onRemove(form.id)} className="text-slate-400 hover:text-red-500 transition-colors">
          <Trash2 className="h-4 w-4" />
        </button>
      )}
    </div>

    <div className="grid grid-cols-2 gap-3">
      <div className="col-span-2">
        <label className="block text-xs text-slate-500 mb-1">Name</label>
        <input
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="e.g. Option A — 25yr @ 4.5%"
          value={form.name}
          onChange={(e) => onChange(form.id, 'name', e.target.value)}
        />
      </div>

      <div>
        <label className="block text-xs text-slate-500 mb-1">Type</label>
        <select
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={form.type}
          onChange={(e) => onChange(form.id, 'type', e.target.value)}
        >
          <option value="LOAN_AMORTIZATION">Loan / Mortgage</option>
          <option value="SINKING_FUND">Sinking Fund</option>
        </select>
      </div>

      <div>
        <label className="block text-xs text-slate-500 mb-1">Frequency</label>
        <select
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={form.payment_frequency}
          onChange={(e) => onChange(form.id, 'payment_frequency', e.target.value)}
        >
          {(Object.keys(FREQ_LABELS) as FrequencyOption[]).map((f) => (
            <option key={f} value={f}>{FREQ_LABELS[f]}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs text-slate-500 mb-1">
          {form.type === 'LOAN_AMORTIZATION' ? 'Principal ($)' : 'Target ($)'}
        </label>
        <input
          type="number"
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="350000"
          value={form.principal}
          onChange={(e) => onChange(form.id, 'principal', e.target.value)}
        />
      </div>

      <div>
        <label className="block text-xs text-slate-500 mb-1">Annual Rate (%)</label>
        <input
          type="number"
          step="0.01"
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="4.5"
          value={form.annual_rate}
          onChange={(e) => onChange(form.id, 'annual_rate', e.target.value)}
        />
      </div>

      <div>
        <label className="block text-xs text-slate-500 mb-1">Amortization (years)</label>
        <input
          type="number"
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="25"
          value={form.amortization_years}
          onChange={(e) => onChange(form.id, 'amortization_years', e.target.value)}
        />
      </div>

      <div>
        <label className="block text-xs text-slate-500 mb-1">Start Date</label>
        <input
          type="date"
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={form.start_date}
          onChange={(e) => onChange(form.id, 'start_date', e.target.value)}
        />
      </div>

      {form.type === 'SINKING_FUND' && (
        <div>
          <label className="block text-xs text-slate-500 mb-1">Current Balance ($)</label>
          <input
            type="number"
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="0"
            value={form.current_balance}
            onChange={(e) => onChange(form.id, 'current_balance', e.target.value)}
          />
        </div>
      )}
    </div>
  </div>
);

// ─── Committed Schedules Panel ────────────────────────────────────────────────

const CommittedSchedules: React.FC<{ schedules: AnnuityScheduleListOut[]; onDelete: (id: number) => void }> = ({
  schedules,
  onDelete,
}) => {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [scheduleDetailsById, setScheduleDetailsById] = useState<Record<number, AnnuityScheduleOut>>({});
  const [loadingDetailsById, setLoadingDetailsById] = useState<Record<number, boolean>>({});
  const [detailErrorsById, setDetailErrorsById] = useState<Record<number, string>>({});

  const handleToggle = async (scheduleId: number) => {
    if (expanded === scheduleId) {
      setExpanded(null);
      return;
    }

    setExpanded(scheduleId);
    if (scheduleDetailsById[scheduleId] || loadingDetailsById[scheduleId]) {
      return;
    }

    setLoadingDetailsById((prev) => ({ ...prev, [scheduleId]: true }));
    setDetailErrorsById((prev) => ({ ...prev, [scheduleId]: '' }));

    try {
      const details = await fetchSchedule(scheduleId);
      setScheduleDetailsById((prev) => ({ ...prev, [scheduleId]: details }));
    } catch (e: unknown) {
      setDetailErrorsById((prev) => ({
        ...prev,
        [scheduleId]: e instanceof Error ? e.message : 'Failed to load schedule details',
      }));
    } finally {
      setLoadingDetailsById((prev) => ({ ...prev, [scheduleId]: false }));
    }
  };

  if (schedules.length === 0) return null;

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-slate-700 flex items-center gap-2">
        <BookMarked className="h-5 w-5 text-slate-500" />
        Committed Schedules
      </h2>
      <div className="space-y-2">
        {schedules.map((s) => (
          <div key={s.id} className="border border-slate-200 rounded-xl bg-white overflow-hidden">
            <div
              className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors"
                onClick={() => { void handleToggle(s.id); }}
            >
              <div className="flex items-center gap-3">
                <div>
                  <span className="font-medium text-slate-800">{s.name}</span>
                  <span className="ml-2 text-xs text-slate-400">
                    {s.schedule_type === 'LOAN_AMORTIZATION' ? 'Loan' : 'Sinking Fund'}
                    {' · '}started {s.start_date}
                    {' · '}{s.n_periods} periods
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <div className="font-semibold text-slate-800">{fmt(s.computed_payment)}<span className="text-xs text-slate-400 font-normal"> / period</span></div>
                  <div className="text-xs text-slate-400">{s.annual_rate}% annual · {s.payment_frequency.toLowerCase()}</div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); if (window.confirm(`Delete "${s.name}"?`)) onDelete(s.id); }}
                  className="text-slate-300 hover:text-red-500 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
                {expanded === s.id ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
              </div>
            </div>

            {expanded === s.id && (
              <div className="border-t border-slate-100 px-4 pb-4">
                {loadingDetailsById[s.id] && (
                  <div className="py-3 text-xs text-slate-500">Loading schedule details...</div>
                )}
                {!!detailErrorsById[s.id] && (
                  <div className="py-3 text-xs text-red-600">{detailErrorsById[s.id]}</div>
                )}
                {!loadingDetailsById[s.id] && !detailErrorsById[s.id] && scheduleDetailsById[s.id]?.periods?.length ? (
                  <ScheduleTable
                    schedule={scheduleDetailsById[s.id].periods.map((p) => ({
                      period_number: p.period_number,
                      payment_date: p.payment_date,
                      payment_amount: p.payment_amount,
                      interest_portion: p.interest_portion,
                      principal_portion: p.principal_portion,
                      balance_after: p.balance_after,
                    }))}
                    type={s.schedule_type as 'LOAN_AMORTIZATION' | 'SINKING_FUND'}
                  />
                ) : null}
                {!loadingDetailsById[s.id] && !detailErrorsById[s.id] && !scheduleDetailsById[s.id]?.periods?.length && (
                  <div className="py-3 text-xs text-slate-500">No periods available for this schedule.</div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── Main Page ────────────────────────────────────────────────────────────────

export const SimulationPage: React.FC = () => {
  const [forms, setForms] = useState<ScenarioForm[]>([defaultForm()]);
  const [results, setResults] = useState<ScenarioResult[] | null>(null);
  const [resultSpecs, setResultSpecs] = useState<ScenarioSpec[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [committedSchedules, setCommittedSchedules] = useState<AnnuityScheduleListOut[]>([]);

  const loadSchedules = useCallback(async () => {
    try {
      const data = await fetchSchedules();
      setCommittedSchedules(data);
    } catch {
      // not critical — page still works for simulation
    }
  }, []);

  useEffect(() => { loadSchedules(); }, [loadSchedules]);

  const handleChange = useCallback((id: string, field: keyof ScenarioForm, value: string) => {
    setForms((prev) => prev.map((f) => (f.id === id ? { ...f, [field]: value } : f)));
  }, []);

  const handleAddScenario = () => setForms((prev) => [...prev, defaultForm()]);
  const handleRemove = (id: string) => setForms((prev) => prev.filter((f) => f.id !== id));

  const handleSimulate = async () => {
    setError(null);
    setLoading(true);
    try {
      const specs: ScenarioSpec[] = forms.map((f) => ({
        name: f.name || `Scenario ${forms.indexOf(f) + 1}`,
        type: f.type,
        principal: parseFloat(f.principal),
        annual_rate: parseFloat(f.annual_rate),
        amortization_years: parseInt(f.amortization_years, 10),
        payment_frequency: f.payment_frequency,
        start_date: f.start_date,
        current_balance: parseFloat(f.current_balance || '0'),
      }));
      const data = await simulateScenarios(specs);
      setResults(data);
      setResultSpecs(specs);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Simulation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    await deleteSchedule(id);
    setCommittedSchedules((prev) => prev.filter((s) => s.id !== id));
  };

  const canSimulate = forms.every(
    (f) => f.principal && f.annual_rate && f.amortization_years && f.start_date
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Calculator className="h-6 w-6 text-blue-600" />
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Scenario Simulator</h1>
          <p className="text-sm text-slate-500">
            Compare N loan or savings scenarios — see the PMT, total interest, and FCF impact.
            The <strong>start date</strong> is the origination date; all payment dates flow from it.
          </p>
        </div>
      </div>

      {/* Forms */}
      <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${Math.min(forms.length, 3)}, 1fr)` }}>
        {forms.map((form, i) => (
          <FormCard
            key={form.id}
            form={form}
            index={i}
            canRemove={forms.length > 1}
            onChange={handleChange}
            onRemove={handleRemove}
          />
        ))}
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        {forms.length < 5 && (
          <button
            onClick={handleAddScenario}
            className="flex items-center gap-2 border border-dashed border-slate-300 rounded-xl px-4 py-2 text-sm text-slate-500 hover:border-blue-400 hover:text-blue-600 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add scenario
          </button>
        )}
        <button
          onClick={handleSimulate}
          disabled={!canSimulate || loading}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-xl px-5 py-2 text-sm font-medium transition-colors"
        >
          <Calculator className="h-4 w-4" />
          {loading ? 'Computing…' : 'Run Simulation'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">{error}</div>
      )}

      {/* Results */}
      {results && results.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-slate-700">Results</h2>

          {/* Summary bar */}
          <div className="bg-white border border-slate-200 rounded-xl p-4">
            <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${results.length}, 1fr)` }}>
              {results.map((r) => (
                <div key={r.name} className="text-center">
                  <div className="text-xs text-slate-500 mb-1 truncate" title={r.name}>{r.name}</div>
                  <div className="text-xl font-bold text-slate-800">{fmt(r.payment_amount)}</div>
                  <div className="text-xs text-slate-500">per period</div>
                  {r.delta_vs_baseline !== null && (
                    <div className={`text-xs mt-1 font-medium ${r.delta_vs_baseline > 0 ? 'text-red-500' : 'text-emerald-600'}`}>
                      {r.delta_vs_baseline > 0 ? '+' : ''}{fmt(r.delta_vs_baseline)} vs baseline
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Full result cards */}
          <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${Math.min(results.length, 3)}, 1fr)` }}>
            {results.map((result, i) => (
              <ResultCard
                key={result.name}
                result={result}
                spec={resultSpecs[i]}
                isBaseline={i === 0}
                index={i}
                onCommitted={loadSchedules}
              />
            ))}
          </div>
        </div>
      )}

      {/* Committed schedules */}
      <CommittedSchedules schedules={committedSchedules} onDelete={handleDelete} />
    </div>
  );
};
