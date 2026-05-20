import React, { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Circle, Settings2, Loader2, ChevronsUp, AlertCircle, Link2 } from 'lucide-react'
import {
  fetchSchedule, payPeriod, bulkPayPeriods, fetchAccountsWithType, updateScheduleRule,
  AnnuityScheduleOut, AnnuityPeriodOut, AccountFlat, BulkPayIn, LinkedRule,
} from '../api/client'

const fmt = (n: number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 2 }).format(n)

const fmtShort = (n: number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(n)

const STORAGE_KEY = (id: number) => `loan-accounts-${id}`

interface StoredAccounts {
  cash_account_id: number
  loan_account_id: number
  interest_account_id: number
}

// ── Account setup panel ───────────────────────────────────────────────────────

interface AccountSetupProps {
  scheduleId: number
  accounts: AccountFlat[]
  stored: StoredAccounts | null
  onSave: (v: StoredAccounts) => void
  onClose: () => void
}

function AccountSetupPanel({ scheduleId, accounts, stored, onSave, onClose }: AccountSetupProps) {
  const [cash, setCash] = useState(String(stored?.cash_account_id ?? ''))
  const [loan, setLoan] = useState(String(stored?.loan_account_id ?? ''))
  const [interest, setInterest] = useState(String(stored?.interest_account_id ?? ''))

  function handleSave(e: React.FormEvent) {
    e.preventDefault()
    if (!cash || !loan || !interest) return
    const v: StoredAccounts = {
      cash_account_id: parseInt(cash),
      loan_account_id: parseInt(loan),
      interest_account_id: parseInt(interest),
    }
    localStorage.setItem(STORAGE_KEY(scheduleId), JSON.stringify(v))
    onSave(v)
  }

  function AccountSel({
    label, hint, types, value, onChange,
  }: { label: string; hint?: string; types: string[]; value: string; onChange: (v: string) => void }) {
    const filtered = accounts.filter(a => types.includes(a.account_type))
    return (
      <div>
        <label className="block text-xs font-medium text-slate-600 mb-1">
          {label}{hint && <span className="ml-1 text-slate-400 font-normal">{hint}</span>}
        </label>
        <select
          required
          className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
          value={value}
          onChange={e => onChange(e.target.value)}
        >
          <option value="">— select —</option>
          {filtered.map(a => (
            <option key={a.id} value={String(a.id)}>{a.name}</option>
          ))}
        </select>
      </div>
    )
  }

  return (
    <div className="bg-white border border-blue-200 rounded-lg p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
          <Settings2 className="w-4 h-4 text-slate-400" />
          Payment accounts
        </p>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xs">cancel</button>
      </div>
      <p className="text-xs text-slate-500 mb-3">
        Set once per session. Used when recording payments (DR loan payable + DR interest, CR cash).
      </p>
      <form onSubmit={handleSave} className="space-y-3">
        <AccountSel label="Cash / Bank" hint="(ASSET — CR)" types={['ASSET']} value={cash} onChange={setCash} />
        <AccountSel label="Loan Payable" hint="(LIABILITY — DR)" types={['LIABILITY']} value={loan} onChange={setLoan} />
        <AccountSel label="Interest Expense" hint="(EXPENSE — DR)" types={['EXPENSE']} value={interest} onChange={setInterest} />
        <button
          type="submit"
          className="w-full py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
        >
          Save
        </button>
      </form>
    </div>
  )
}

// ── Period row ────────────────────────────────────────────────────────────────

interface PeriodRowProps {
  period: AnnuityPeriodOut
  scheduleType: string
  recording: boolean
  onPay: (period: AnnuityPeriodOut) => void
}

function PeriodRow({ period, scheduleType, recording, onPay }: PeriodRowProps) {
  const today = new Date().toISOString().slice(0, 10)
  const isPast = period.payment_date <= today

  return (
    <tr className={`border-t border-slate-100 text-sm ${period.is_paid ? 'opacity-60' : ''}`}>
      <td className="py-2 px-3 text-slate-500 text-xs">{period.period_number}</td>
      <td className="py-2 px-3 text-slate-700">{period.payment_date}</td>
      <td className="py-2 px-3 text-right text-slate-800 font-medium">{fmt(Number(period.payment_amount))}</td>
      <td className="py-2 px-3 text-right text-red-500">{fmt(Number(period.interest_portion))}</td>
      <td className="py-2 px-3 text-right text-emerald-600">{fmt(Number(period.principal_portion))}</td>
      <td className="py-2 px-3 text-right text-slate-600">{fmtShort(Number(period.balance_after))}</td>
      <td className="py-2 px-3 text-center">
        {period.is_paid ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-500 mx-auto" />
        ) : (
          <Circle className="w-4 h-4 text-slate-300 mx-auto" />
        )}
      </td>
      <td className="py-2 px-3 text-right">
        {!period.is_paid && (
          <button
            onClick={() => onPay(period)}
            disabled={recording}
            className={`text-xs px-2 py-0.5 rounded transition-colors ${
              isPast
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'border border-blue-400 text-blue-600 hover:bg-blue-50'
            } disabled:opacity-40`}
          >
            {recording ? '…' : 'Record'}
          </button>
        )}
        {period.is_paid && period.journal_entry_id && (
          <span className="text-xs text-slate-400">JE #{period.journal_entry_id}</span>
        )}
      </td>
    </tr>
  )
}

// ── Statement matching panel ──────────────────────────────────────────────────

interface StatementMatchingProps {
  scheduleId: number
  rule: LinkedRule | null
  computedPayment: number
  onUpdated: (updated: AnnuityScheduleOut) => void
  onClose: () => void
}

function StatementMatchingPanel({ scheduleId, rule, computedPayment, onUpdated, onClose }: StatementMatchingProps) {
  const [text, setText] = useState(rule?.search_text ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    setSaving(true)
    setError(null)
    try {
      const updated = await updateScheduleRule(scheduleId, text.trim())
      onUpdated(updated)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-white border border-indigo-200 rounded-lg p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
          <Link2 className="w-4 h-4 text-indigo-400" />
          Statement auto-matching
        </p>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xs">cancel</button>
      </div>

      <p className="text-xs text-slate-500 mb-3">
        Enter the merchant string exactly as it appears on bank statements (case-insensitive substring match).
        When a transaction matches, the payment is automatically split into principal&nbsp;+&nbsp;interest entries
        instead of routing to a single expense account.
      </p>

      {rule && (
        <div className="mb-3 text-xs text-slate-500 bg-slate-50 rounded px-3 py-2 space-y-0.5">
          <div>Current match string: <code className="font-mono text-slate-700">"{rule.search_text}"</code></div>
          <div>Amount window: <span className="text-slate-700">{rule.min_amount !== null ? `${fmt(rule.min_amount)} – ${fmt(rule.max_amount!)}` : 'any amount'}</span></div>
          <div>Intercepting merchant: <span className="text-slate-700">{rule.merchant_name}</span></div>
        </div>
      )}

      <form onSubmit={handleSave} className="flex gap-2">
        <input
          required
          className="flex-1 border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-400 font-mono"
          placeholder={`e.g. "toyota financial" or "honda financial services"`}
          value={text}
          onChange={e => setText(e.target.value)}
        />
        <button
          type="submit"
          disabled={saving}
          className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </form>

      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}

      <p className="text-[10px] text-slate-400 mt-2">
        Amount window is fixed at ±$5 of the computed payment ({fmt(computedPayment)}) and cannot be changed here.
        Priority: amount-bound rules always beat plain-text rules, so this rule will intercept the payment even if a broader expense rule also matches.
      </p>
    </div>
  )
}


// ── Main page ─────────────────────────────────────────────────────────────────

export function LoanDetailPage() {
  const { id } = useParams<{ id: string }>()
  const scheduleId = parseInt(id!)

  const [schedule, setSchedule] = useState<AnnuityScheduleOut | null>(null)
  const [accounts, setAccounts] = useState<AccountFlat[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [recording, setRecording] = useState<number | null>(null)  // period id being recorded
  const [bulkRecording, setBulkRecording] = useState(false)
  const [storedAccounts, setStoredAccounts] = useState<StoredAccounts | null>(null)
  const [showAccountSetup, setShowAccountSetup] = useState(false)
  const [showMatchingPanel, setShowMatchingPanel] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY(scheduleId))
    if (saved) {
      try { setStoredAccounts(JSON.parse(saved)) } catch {}
    }
    Promise.all([fetchSchedule(scheduleId), fetchAccountsWithType()])
      .then(([s, a]) => { setSchedule(s); setAccounts(a) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [scheduleId])

  async function handlePayPeriod(period: AnnuityPeriodOut) {
    if (!storedAccounts) {
      setShowAccountSetup(true)
      return
    }
    setRecording(period.id)
    setActionError(null)
    try {
      const updated = await payPeriod(scheduleId, period.id, {
        cash_account_id: storedAccounts.cash_account_id,
        loan_account_id: storedAccounts.loan_account_id,
        interest_account_id: storedAccounts.interest_account_id,
      })
      setSchedule(updated)
    } catch (e: any) {
      setActionError(e.message)
    } finally {
      setRecording(null)
    }
  }

  async function handleBulkPay() {
    if (!storedAccounts || !schedule) return
    const pastUnpaid = schedule.periods.filter(
      p => !p.is_paid && p.payment_date <= new Date().toISOString().slice(0, 10)
    )
    if (pastUnpaid.length === 0) {
      setActionError('No past unpaid periods found.')
      return
    }
    if (!window.confirm(`Record ${pastUnpaid.length} past payment(s) as paid?`)) return
    setBulkRecording(true)
    setActionError(null)
    try {
      const payload: BulkPayIn = {
        period_ids: pastUnpaid.map(p => p.id),
        cash_account_id: storedAccounts.cash_account_id,
        loan_account_id: storedAccounts.loan_account_id,
        interest_account_id: storedAccounts.interest_account_id,
      }
      const updated = await bulkPayPeriods(scheduleId, payload)
      setSchedule(updated)
    } catch (e: any) {
      setActionError(e.message)
    } finally {
      setBulkRecording(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    )
  }

  if (error || !schedule) {
    return (
      <div className="text-center py-16 space-y-2">
        <p className="text-red-600 text-sm">{error || 'Schedule not found'}</p>
        <Link to="/dashboard/simulate" className="text-blue-600 text-sm hover:underline">← Back</Link>
      </div>
    )
  }

  const periods = schedule.periods
  const paidCount = periods.filter(p => p.is_paid).length
  const paidPrincipal = periods.filter(p => p.is_paid).reduce((s, p) => s + Number(p.principal_portion), 0)
  const paidInterest = periods.filter(p => p.is_paid).reduce((s, p) => s + Number(p.interest_portion), 0)
  const remainingBalance = periods.filter(p => !p.is_paid).reduce(
    (_, p, i, arr) => (i === 0 ? Number(p.balance_after) + Number(p.principal_portion) : _),
    Number(schedule.principal_amount)
  )
  const pastUnpaidCount = periods.filter(
    p => !p.is_paid && p.payment_date <= new Date().toISOString().slice(0, 10)
  ).length

  const displayPeriods = showAll ? periods : periods.slice(0, 24)

  return (
    <div className="space-y-5">
      <Link to="/dashboard/simulate" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Simulation / Schedules
      </Link>

      {/* Header */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-5">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">{schedule.name}</h1>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
              <span>{schedule.schedule_type === 'LOAN_AMORTIZATION' ? 'Loan amortization' : 'Sinking fund'}</span>
              <span>Principal: <strong className="text-slate-700">{fmtShort(Number(schedule.principal_amount))}</strong></span>
              <span>Rate: <strong className="text-slate-700">{Number(schedule.annual_rate)}%</strong></span>
              <span>Payment: <strong className="text-slate-700">{fmt(Number(schedule.computed_payment))} / {schedule.payment_frequency.toLowerCase().replace('biweekly', 'bi-wk')}</strong></span>
              <span>{schedule.n_periods} periods · started {schedule.start_date}</span>
            </div>
            {schedule.linked_journal_entry_id && (
              <p className="mt-1 text-xs text-blue-500">Purchase JE #{schedule.linked_journal_entry_id} linked</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setShowMatchingPanel(v => !v); setShowAccountSetup(false); setActionError(null) }}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded border transition-colors ${
                schedule.linked_rule
                  ? 'border-indigo-300 text-indigo-700 bg-indigo-50'
                  : 'border-amber-300 text-amber-700 bg-amber-50'
              }`}
            >
              <Link2 className="w-3.5 h-3.5" />
              {schedule.linked_rule ? 'Statement matched' : 'Set statement match'}
            </button>
            <button
              onClick={() => { setShowAccountSetup(v => !v); setShowMatchingPanel(false); setActionError(null) }}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded border transition-colors ${
                storedAccounts ? 'border-emerald-300 text-emerald-700 bg-emerald-50' : 'border-slate-300 text-slate-500 hover:bg-slate-50'
              }`}
            >
              <Settings2 className="w-3.5 h-3.5" />
              {storedAccounts ? 'Accounts set' : 'Set accounts'}
            </button>
          </div>
        </div>
      </div>

      {/* Statement matching panel */}
      {showMatchingPanel && (
        <StatementMatchingPanel
          scheduleId={scheduleId}
          rule={schedule.linked_rule}
          computedPayment={Number(schedule.computed_payment)}
          onUpdated={s => { setSchedule(s); setShowMatchingPanel(false) }}
          onClose={() => setShowMatchingPanel(false)}
        />
      )}

      {/* Account setup panel */}
      {showAccountSetup && (
        <AccountSetupPanel
          scheduleId={scheduleId}
          accounts={accounts}
          stored={storedAccounts}
          onSave={v => { setStoredAccounts(v); setShowAccountSetup(false) }}
          onClose={() => setShowAccountSetup(false)}
        />
      )}

      {/* Error banner */}
      {actionError && (
        <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-md">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          {actionError}
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">Paid</p>
          <p className="text-xl font-bold text-slate-900 mt-1">{paidCount} <span className="text-sm font-normal text-slate-400">/ {periods.length}</span></p>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">Principal repaid</p>
          <p className="text-xl font-bold text-emerald-700 mt-1">{fmtShort(paidPrincipal)}</p>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">Interest paid</p>
          <p className="text-xl font-bold text-red-500 mt-1">{fmtShort(paidInterest)}</p>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">Outstanding balance</p>
          <p className="text-xl font-bold text-slate-900 mt-1">{fmtShort(remainingBalance)}</p>
        </div>
      </div>

      {/* Bulk catch-up */}
      {pastUnpaidCount > 0 && (
        <div className="flex items-center justify-between bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
          <div className="text-sm text-amber-800">
            <strong>{pastUnpaidCount}</strong> past payment{pastUnpaidCount !== 1 ? 's' : ''} not yet recorded in the ledger.
          </div>
          <button
            onClick={handleBulkPay}
            disabled={bulkRecording || !storedAccounts}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-amber-600 text-white rounded hover:bg-amber-700 disabled:opacity-40 transition-colors"
          >
            <ChevronsUp className="w-3.5 h-3.5" />
            {bulkRecording ? 'Recording…' : `Catch up ${pastUnpaidCount} payment${pastUnpaidCount !== 1 ? 's' : ''}`}
          </button>
        </div>
      )}

      {/* Amortization table */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
          <h2 className="font-semibold text-slate-800">Amortization schedule</h2>
          <span className="text-xs text-slate-400">{paidCount} of {periods.length} recorded</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs font-medium text-slate-500 uppercase tracking-wide bg-slate-50">
                <th className="py-2.5 px-3 text-left">#</th>
                <th className="py-2.5 px-3 text-left">Date</th>
                <th className="py-2.5 px-3 text-right">Payment</th>
                <th className="py-2.5 px-3 text-right">Interest</th>
                <th className="py-2.5 px-3 text-right">Principal</th>
                <th className="py-2.5 px-3 text-right">Balance</th>
                <th className="py-2.5 px-3 text-center">Paid</th>
                <th className="py-2.5 px-3 text-right"></th>
              </tr>
            </thead>
            <tbody>
              {displayPeriods.map(p => (
                <PeriodRow
                  key={p.id}
                  period={p}
                  scheduleType={schedule.schedule_type}
                  recording={recording === p.id}
                  onPay={handlePayPeriod}
                />
              ))}
            </tbody>
          </table>
        </div>
        {periods.length > 24 && (
          <div className="px-5 py-3 border-t border-slate-100 text-center">
            <button
              onClick={() => setShowAll(v => !v)}
              className="text-xs text-blue-600 hover:text-blue-800 transition-colors"
            >
              {showAll ? `Show first 24 periods` : `Show all ${periods.length} periods`}
            </button>
          </div>
        )}
      </div>

      {!storedAccounts && (
        <p className="text-xs text-slate-400 text-center">
          Click "Set accounts" above to configure the ledger accounts used when recording payments.
        </p>
      )}
    </div>
  )
}
