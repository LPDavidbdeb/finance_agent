import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Car, CreditCard, Building2, AlertCircle } from 'lucide-react'
import { loanSetup, fetchAccountsWithType, AccountFlat, LoanSetupIn } from '../api/client'

const fmt = (n: number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(n)

type Frequency = 'MONTHLY' | 'BIWEEKLY' | 'WEEKLY' | 'ANNUALLY'

const FREQ_LABELS: Record<Frequency, string> = {
  MONTHLY: 'Monthly',
  BIWEEKLY: 'Bi-weekly',
  WEEKLY: 'Weekly',
  ANNUALLY: 'Annual',
}

interface FormState {
  // Asset
  purchase_description: string
  purchase_date: string
  purchase_price: string
  down_payment: string
  loan_amount: string
  // Schedule
  schedule_name: string
  annual_rate: string
  amortization_years: string
  payment_frequency: Frequency
  schedule_start_date: string
  // Accounts
  asset_account_id: string
  cash_account_id: string
  loan_account_id: string
}

const EMPTY: FormState = {
  purchase_description: '',
  purchase_date: new Date().toISOString().slice(0, 10),
  purchase_price: '',
  down_payment: '0',
  loan_amount: '',
  schedule_name: '',
  annual_rate: '',
  amortization_years: '5',
  payment_frequency: 'BIWEEKLY',
  schedule_start_date: '',
  asset_account_id: '',
  cash_account_id: '',
  loan_account_id: '',
}

function AccountSelect({
  label,
  hint,
  types,
  accounts,
  value,
  onChange,
}: {
  label: string
  hint?: string
  types: string[]
  accounts: AccountFlat[]
  value: string
  onChange: (v: string) => void
}) {
  const filtered = accounts.filter(a => types.includes(a.account_type))
  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 mb-1">
        {label}
        {hint && <span className="ml-1 text-slate-400 font-normal">{hint}</span>}
      </label>
      <select
        required
        className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
        value={value}
        onChange={e => onChange(e.target.value)}
      >
        <option value="">— select account —</option>
        {filtered.map(a => (
          <option key={a.id} value={String(a.id)}>
            {'  '.repeat((a as any).depth ?? 0)}{a.name}
          </option>
        ))}
      </select>
    </div>
  )
}

export function LoanSetupPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState<FormState>(EMPTY)
  const [accounts, setAccounts] = useState<AccountFlat[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchAccountsWithType().then(setAccounts).catch(() => {})
  }, [])

  function set(field: keyof FormState, value: string) {
    setForm(f => {
      const next = { ...f, [field]: value }
      // Auto-derive loan_amount and schedule_name from purchase details
      if (field === 'purchase_price' || field === 'down_payment') {
        const price = parseFloat(field === 'purchase_price' ? value : f.purchase_price) || 0
        const down = parseFloat(field === 'down_payment' ? value : f.down_payment) || 0
        next.loan_amount = String(Math.max(0, price - down))
      }
      if (field === 'purchase_description' && !f.schedule_name) {
        next.schedule_name = value ? `${value} — Auto Loan` : ''
      }
      return next
    })
  }

  const loanAmt = parseFloat(form.loan_amount) || 0
  const price = parseFloat(form.purchase_price) || 0
  const down = parseFloat(form.down_payment) || 0
  const rate = parseFloat(form.annual_rate) || 0
  const years = parseInt(form.amortization_years) || 0

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.asset_account_id || !form.cash_account_id || !form.loan_account_id) {
      setError('Please select all three accounts.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const payload: LoanSetupIn = {
        purchase_description: form.purchase_description,
        purchase_date: form.purchase_date,
        purchase_price: price,
        down_payment: down,
        loan_amount: loanAmt,
        asset_account_id: parseInt(form.asset_account_id),
        cash_account_id: parseInt(form.cash_account_id),
        loan_account_id: parseInt(form.loan_account_id),
        schedule_name: form.schedule_name || form.purchase_description,
        annual_rate: rate,
        amortization_years: years,
        payment_frequency: form.payment_frequency,
        schedule_start_date: form.schedule_start_date,
      }
      const schedule = await loanSetup(payload)
      navigate(`/dashboard/loans/${schedule.id}`)
    } catch (e: any) {
      setError(e.message)
      setSaving(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Register a Financed Purchase</h1>
        <p className="text-sm text-slate-500 mt-1">
          Records the asset on your balance sheet, creates the loan liability, and generates the full amortization schedule.
        </p>
      </div>

      {error && (
        <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-md">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">

        {/* Section 1 — Asset */}
        <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4">
          <div className="flex items-center gap-2 text-slate-700 font-semibold text-sm">
            <Car className="w-4 h-4" />
            Asset details
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-600 mb-1">Description</label>
              <input
                required
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                placeholder="e.g. Honda Civic 2024"
                value={form.purchase_description}
                onChange={e => set('purchase_description', e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Purchase date</label>
              <input
                required
                type="date"
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.purchase_date}
                onChange={e => set('purchase_date', e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Purchase price</label>
              <input
                required
                type="number"
                min="0"
                step="0.01"
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                placeholder="35000"
                value={form.purchase_price}
                onChange={e => set('purchase_price', e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Down payment</label>
              <input
                type="number"
                min="0"
                step="0.01"
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                placeholder="0"
                value={form.down_payment}
                onChange={e => set('down_payment', e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Loan amount
                <span className="ml-1 text-slate-400 font-normal">(auto-calculated; adjust if needed)</span>
              </label>
              <input
                required
                type="number"
                min="0"
                step="0.01"
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.loan_amount}
                onChange={e => set('loan_amount', e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Section 2 — Loan Terms */}
        <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4">
          <div className="flex items-center gap-2 text-slate-700 font-semibold text-sm">
            <CreditCard className="w-4 h-4" />
            Loan terms
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-600 mb-1">Schedule name</label>
              <input
                required
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                placeholder="e.g. Honda Civic 2024 — Auto Loan"
                value={form.schedule_name}
                onChange={e => set('schedule_name', e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Annual interest rate (%)</label>
              <input
                required
                type="number"
                min="0"
                max="30"
                step="0.01"
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                placeholder="5.99"
                value={form.annual_rate}
                onChange={e => set('annual_rate', e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Amortization (years)</label>
              <input
                required
                type="number"
                min="1"
                max="30"
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.amortization_years}
                onChange={e => set('amortization_years', e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Payment frequency</label>
              <select
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.payment_frequency}
                onChange={e => set('payment_frequency', e.target.value)}
              >
                {(Object.keys(FREQ_LABELS) as Frequency[]).map(f => (
                  <option key={f} value={f}>{FREQ_LABELS[f]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                First payment date
                <span className="ml-1 text-slate-400 font-normal">(loan origination anchor)</span>
              </label>
              <input
                required
                type="date"
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.schedule_start_date}
                onChange={e => set('schedule_start_date', e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Section 3 — Accounts */}
        <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4">
          <div className="flex items-center gap-2 text-slate-700 font-semibold text-sm">
            <Building2 className="w-4 h-4" />
            Chart of accounts mapping
          </div>
          <p className="text-xs text-slate-500">
            These map to the three lines of the purchase journal entry:
            <strong className="text-slate-600"> DR</strong> {form.purchase_description || 'asset'} /{' '}
            {down > 0 && <><strong className="text-slate-600">CR</strong> Bank {fmt(down)} /{' '}</>}
            <strong className="text-slate-600">CR</strong> Loan payable {fmt(loanAmt)}
          </p>
          <div className="grid grid-cols-1 gap-4">
            <AccountSelect
              label="Vehicle / Asset account"
              hint="(ASSET type — debited for the purchase price)"
              types={['ASSET']}
              accounts={accounts}
              value={form.asset_account_id}
              onChange={v => set('asset_account_id', v)}
            />
            <AccountSelect
              label="Cash / Bank account"
              hint="(ASSET type — credited for the down payment)"
              types={['ASSET']}
              accounts={accounts}
              value={form.cash_account_id}
              onChange={v => set('cash_account_id', v)}
            />
            <AccountSelect
              label="Loan Payable account"
              hint="(LIABILITY type — must already exist in your chart of accounts)"
              types={['LIABILITY']}
              accounts={accounts}
              value={form.loan_account_id}
              onChange={v => set('loan_account_id', v)}
            />
          </div>
          {accounts.filter(a => a.account_type === 'LIABILITY').length === 0 && (
            <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 text-amber-700 text-xs px-3 py-2 rounded">
              <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              No LIABILITY accounts found. Create one in the Ledger (e.g. "Auto Loan — Honda Civic") before proceeding.
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="px-4 py-2 text-sm border rounded-md hover:bg-slate-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="px-5 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
          >
            {saving ? 'Creating…' : 'Create purchase entry & schedule →'}
          </button>
        </div>
      </form>
    </div>
  )
}
