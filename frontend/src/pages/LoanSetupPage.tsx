import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Car, CreditCard, Building2, AlertCircle, Calculator, Info, Plus, FileText, X } from 'lucide-react'
import { 
  loanSetup, fetchAccountsWithType, AccountFlat, LoanSetupIn, 
  simulateScenarios, ScenarioResult, ScenarioSpec 
} from '../api/client'

const fmt = (n: number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(n)

const fmtDetailed = (n: number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 2 }).format(n)

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
  new_loan_account_name: string
  create_new_loan_account: boolean
  // Documents
  sales_contract: File | null
  financing_contract: File | null
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
  schedule_start_date: new Date().toISOString().slice(0, 10),
  asset_account_id: '',
  cash_account_id: '',
  loan_account_id: '',
  new_loan_account_name: '',
  create_new_loan_account: false,
  sales_contract: null,
  financing_contract: null,
}

function AccountSelect({
  label,
  hint,
  types,
  accounts,
  value,
  onChange,
  onNewAccount,
}: {
  label: string
  hint?: string
  types: string[]
  accounts: AccountFlat[]
  value: string
  onChange: (v: string) => void
  onNewAccount?: () => void
  isLiability?: boolean
}) {
  const filtered = accounts.filter(a => types.includes(a.account_type))
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="block text-xs font-medium text-slate-600">
          {label}
          {hint && <span className="ml-1 text-slate-400 font-normal">{hint}</span>}
        </label>
        {onNewAccount && (
          <button 
            type="button" 
            onClick={onNewAccount}
            className="text-[10px] text-blue-600 hover:text-blue-800 flex items-center gap-0.5 font-medium"
          >
            <Plus className="w-2.5 h-2.5" />
            Create new
          </button>
        )}
      </div>
      <select
        required={!onNewAccount}
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

function DocumentUpload({
  label,
  description,
  file,
  onFileSelect,
  onFileClear,
  id
}: {
  label: string
  description: string
  file: File | null
  onFileSelect: (f: File) => void
  onFileClear: () => void
  id: string
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  
  return (
    <div className="space-y-2">
      <label className="block text-xs font-medium text-slate-600">{label}</label>
      {!file ? (
        <div 
          onClick={() => inputRef.current?.click()}
          className="border-2 border-dashed border-slate-200 rounded-lg p-4 text-center hover:border-blue-400 hover:bg-blue-50 cursor-pointer transition-all group"
        >
          <input 
            type="file" 
            id={id}
            ref={inputRef}
            className="hidden" 
            accept=".pdf,image/*"
            onChange={e => e.target.files?.[0] && onFileSelect(e.target.files[0])}
          />
          <FileText className="w-6 h-6 text-slate-300 mx-auto mb-1 group-hover:text-blue-500 transition-colors" />
          <p className="text-[10px] font-medium text-slate-600">{description}</p>
        </div>
      ) : (
        <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg p-2">
          <div className="flex items-center gap-2 overflow-hidden text-ellipsis">
            <div className="bg-blue-100 p-1.5 rounded text-blue-600 shrink-0">
              <FileText className="w-3.5 h-3.5" />
            </div>
            <div className="overflow-hidden">
              <p className="text-[10px] font-medium text-slate-700 truncate">{file.name}</p>
              <p className="text-[9px] text-slate-400">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
          </div>
          <button 
            type="button" 
            onClick={onFileClear}
            className="p-1 hover:bg-slate-200 rounded-full text-slate-400 hover:text-slate-600 transition-colors shrink-0"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  )
}

export function LoanSetupPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState<FormState>(EMPTY)
  const [accounts, setAccounts] = useState<AccountFlat[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<ScenarioResult | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)

  useEffect(() => {
    fetchAccountsWithType().then(setAccounts).catch(() => {})
  }, [])

  function set(field: keyof FormState, value: any) {
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
        if (f.create_new_loan_account) {
          next.new_loan_account_name = value ? `Loan: ${value}` : ''
        }
      }
      if (field === 'create_new_loan_account' && value === true && !f.new_loan_account_name) {
        next.new_loan_account_name = f.purchase_description ? `Loan: ${f.purchase_description}` : ''
      }
      return next
    })
  }

  const loanAmt = parseFloat(form.loan_amount) || 0
  const price = parseFloat(form.purchase_price) || 0
  const down = parseFloat(form.down_payment) || 0
  const rate = parseFloat(form.annual_rate) || 0
  const years = parseInt(form.amortization_years) || 0

  // Live Preview Logic
  useEffect(() => {
    if (loanAmt > 0 && rate > 0 && years > 0) {
      const timer = setTimeout(async () => {
        setLoadingPreview(true)
        try {
          const spec: ScenarioSpec = {
            name: 'Preview',
            type: 'LOAN_AMORTIZATION',
            principal: loanAmt,
            annual_rate: rate,
            amortization_years: years,
            payment_frequency: form.payment_frequency,
            start_date: form.schedule_start_date,
          }
          const results = await simulateScenarios([spec])
          setPreview(results[0])
        } catch (e) {
          console.error('Preview failed', e)
        } finally {
          setLoadingPreview(false)
        }
      }, 500)
      return () => clearTimeout(timer)
    } else {
      setPreview(null)
    }
  }, [loanAmt, rate, years, form.payment_frequency, form.schedule_start_date])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.asset_account_id || !form.cash_account_id || (!form.loan_account_id && !form.create_new_loan_account)) {
      setError('Please select all required accounts or provide a new account name.')
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
        loan_account_id: form.create_new_loan_account ? null : parseInt(form.loan_account_id),
        new_loan_account_name: form.create_new_loan_account ? form.new_loan_account_name : null,
        schedule_name: form.schedule_name || form.purchase_description,
        annual_rate: rate,
        amortization_years: years,
        payment_frequency: form.payment_frequency,
        schedule_start_date: form.schedule_start_date,
      }
      const schedule = await loanSetup(payload, form.sales_contract, form.financing_contract)
      navigate(`/dashboard/loans/${schedule.id}`)
    } catch (e: any) {
      setError(e.message)
      setSaving(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-6">
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
          <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4 shadow-sm">
            <div className="flex items-center gap-2 text-slate-700 font-semibold text-sm border-b border-slate-100 pb-3">
              <Car className="w-4 h-4 text-blue-500" />
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
                  Financed amount
                </label>
                <input
                  required
                  type="number"
                  min="0"
                  step="0.01"
                  className="w-full border rounded px-3 py-2 text-sm bg-slate-50 font-medium text-slate-700"
                  readOnly
                  value={form.loan_amount}
                />
              </div>
            </div>
          </div>

          {/* Section 2 — Loan Terms */}
          <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4 shadow-sm">
            <div className="flex items-center gap-2 text-slate-700 font-semibold text-sm border-b border-slate-100 pb-3">
              <CreditCard className="w-4 h-4 text-emerald-500" />
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
          <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4 shadow-sm">
            <div className="flex items-center gap-2 text-slate-700 font-semibold text-sm border-b border-slate-100 pb-3">
              <Building2 className="w-4 h-4 text-amber-500" />
              Chart of accounts mapping
            </div>
            
            <div className="grid grid-cols-1 gap-4">
              <AccountSelect
                label="Vehicle / Asset account"
                hint="(ASSET type — DR)"
                types={['ASSET']}
                accounts={accounts}
                value={form.asset_account_id}
                onChange={v => set('asset_account_id', v)}
              />
              <AccountSelect
                label="Cash / Bank account"
                hint="(ASSET type — CR)"
                types={['ASSET']}
                accounts={accounts}
                value={form.cash_account_id}
                onChange={v => set('cash_account_id', v)}
              />

              <div className="border-t border-slate-100 pt-4 mt-2">
                {form.create_new_loan_account ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <label className="block text-xs font-medium text-slate-600">New Loan Payable Account Name</label>
                      <button 
                        type="button" 
                        onClick={() => set('create_new_loan_account', false)}
                        className="text-[10px] text-slate-500 hover:text-slate-700 underline"
                      >
                        Cancel new account
                      </button>
                    </div>
                    <input
                      required
                      className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                      placeholder="e.g. Loan: Honda Civic 2024"
                      value={form.new_loan_account_name}
                      onChange={e => set('new_loan_account_name', e.target.value)}
                    />
                    <p className="text-[10px] text-slate-400 italic">
                      This will create a new LIABILITY account automatically.
                    </p>
                  </div>
                ) : (
                  <AccountSelect
                    label="Loan Payable account"
                    hint="(LIABILITY type — CR)"
                    types={['LIABILITY']}
                    accounts={accounts}
                    value={form.loan_account_id}
                    onChange={v => set('loan_account_id', v)}
                    onNewAccount={() => set('create_new_loan_account', true)}
                  />
                )}
              </div>
            </div>
          </div>

          {/* Section 4 — Documentation */}
          <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4 shadow-sm">
            <div className="flex items-center gap-2 text-slate-700 font-semibold text-sm border-b border-slate-100 pb-3">
              <FileText className="w-4 h-4 text-slate-500" />
              Contract / Documentation
              <span className="text-[10px] font-normal text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100 uppercase tracking-wider ml-1">Optional</span>
            </div>
            
            <p className="text-xs text-slate-500 mb-2">
              Upload legal documents for both the purchase and the financing. This enables future AI-driven data extraction and auditing.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
              <DocumentUpload 
                id="sales-contract"
                label="Sales Contract / Bill of Sale"
                description="Click to upload asset purchase proof"
                file={form.sales_contract}
                onFileSelect={f => set('sales_contract', f)}
                onFileClear={() => set('sales_contract', null)}
              />
              <DocumentUpload 
                id="financing-contract"
                label="Financing / Loan Agreement"
                description="Click to upload debt terms contract"
                file={form.financing_contract}
                onFileSelect={f => set('financing_contract', f)}
                onFileClear={() => set('financing_contract', null)}
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pb-10">
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
              className="px-5 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium shadow-sm"
            >
              {saving ? 'Creating…' : 'Finalize Purchase & Schedule →'}
            </button>
          </div>
        </form>
      </div>

      {/* Sidebar — Preview */}
      <div className="space-y-6">
        <div className="bg-slate-900 rounded-xl p-6 text-white shadow-xl sticky top-6">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-bold uppercase tracking-wider mb-6">
            <Calculator className="w-4 h-4" />
            Amortization Preview
          </div>

          {preview ? (
            <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
              <div>
                <p className="text-slate-400 text-xs mb-1">Calculated Payment ({FREQ_LABELS[form.payment_frequency]})</p>
                <p className="text-4xl font-bold tracking-tight">{fmtDetailed(preview.payment_amount)}</p>
              </div>

              <div className="grid grid-cols-2 gap-4 border-t border-slate-800 pt-6">
                <div>
                  <p className="text-slate-400 text-[10px] uppercase font-bold mb-1">Total Interest</p>
                  <p className="text-lg font-semibold text-red-400">{fmt(preview.total_interest_paid)}</p>
                </div>
                <div>
                  <p className="text-slate-400 text-[10px] uppercase font-bold mb-1">Total Cost</p>
                  <p className="text-lg font-semibold text-blue-300">{fmt(preview.total_cost)}</p>
                </div>
              </div>

              <div className="bg-slate-800/50 rounded-lg p-4 space-y-3">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Principal</span>
                  <span className="font-medium">{fmt(loanAmt)}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Total Payments</span>
                  <span className="font-medium">{preview.schedule.length}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Final Payment</span>
                  <span className="font-medium">{preview.schedule[preview.schedule.length - 1].payment_date}</span>
                </div>
              </div>

              <div className="flex items-start gap-2 text-[10px] text-slate-500 bg-slate-800/30 p-2 rounded">
                <Info className="w-3 h-3 shrink-0 mt-0.5" />
                This is a stateless projection. No data is saved until you click finalize.
              </div>
            </div>
          ) : (
            <div className="py-12 text-center space-y-4">
              <div className="w-12 h-12 bg-slate-800 rounded-full flex items-center justify-center mx-auto">
                <Calculator className="w-6 h-6 text-slate-600" />
              </div>
              <p className="text-slate-500 text-sm italic">
                {loadingPreview ? 'Calculating...' : 'Enter amount, rate, and years to see your payment schedule.'}
              </p>
            </div>
          )}
        </div>
        
        {/* Ledger Impact visualization */}
        <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm space-y-3">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Accounting Flow</p>
          <div className="space-y-2">
             <div className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
                <div className="flex-1 text-xs">
                   <span className="font-bold">DEBIT</span> Asset Account
                   <div className="text-slate-400">Increase assets by {fmt(price)}</div>
                </div>
             </div>
             <div className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-red-400"></div>
                <div className="flex-1 text-xs">
                   <span className="font-bold">CREDIT</span> Cash Account
                   <div className="text-slate-400">Decrease bank by {fmt(down)}</div>
                </div>
             </div>
             <div className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-amber-400"></div>
                <div className="flex-1 text-xs">
                   <span className="font-bold">CREDIT</span> Loan Account
                   <div className="text-slate-400">Increase liability by {fmt(loanAmt)}</div>
                </div>
             </div>
          </div>
        </div>
      </div>
    </div>
  )
}
