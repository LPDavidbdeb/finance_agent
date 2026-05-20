import React, { useState, useEffect, useRef } from 'react'
import { simulateScenarios, ScenarioSpec, ScenarioResult, PeriodRow, fetchCpiRate } from '../api/client'
import { ExpenseCategoryPanel } from './ExpenseCategoryPanel'

const RATES = [3, 5, 7]  // percent — planning API divides by 100 internally
const FREQS = ['MONTHLY', 'BIWEEKLY'] as const

const cad = new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' })

function buildSpecs(principal: number, years: number, startDate: string): ScenarioSpec[] {
  const specs: ScenarioSpec[] = []
  for (const rate of RATES) {
    for (const freq of FREQS) {
      specs.push({
        name: `${rate}|${freq}`,
        type: 'SINKING_FUND',
        principal,
        annual_rate: rate,
        amortization_years: years,
        payment_frequency: freq,
        start_date: startDate,
      })
    }
  }
  return specs
}

// Walk the schedule and return the accumulated balance as of today
function balanceAsOfToday(schedule: PeriodRow[]): number {
  const today = new Date().toISOString().split('T')[0]
  let balance = 0
  for (const row of schedule) {
    if (row.payment_date <= today) balance = row.balance_after
    else break
  }
  return balance
}

interface RateRow {
  rate: number
  monthly: number
  biweekly: number
  totalContributed: number
  investmentGain: number
  catchUpMonthly: number   // lump sum needed today if no contributions were made since purchase
  catchUpBiweekly: number
}

function parseResults(results: ScenarioResult[]): RateRow[] {
  const map: Record<string, Partial<RateRow>> = {}
  for (const r of results) {
    const [rateStr, freq] = r.name.split('|')
    if (!map[rateStr]) map[rateStr] = { rate: Number(rateStr) }
    if (freq === 'MONTHLY') {
      map[rateStr].monthly = r.payment_amount
      map[rateStr].totalContributed = r.total_cost
      map[rateStr].investmentGain = r.total_interest_paid
      map[rateStr].catchUpMonthly = balanceAsOfToday(r.schedule)
    }
    if (freq === 'BIWEEKLY') {
      map[rateStr].biweekly = r.payment_amount
      map[rateStr].catchUpBiweekly = balanceAsOfToday(r.schedule)
    }
  }
  return RATES.map(rate => ({
    rate,
    monthly:          map[String(rate)]?.monthly          ?? 0,
    biweekly:         map[String(rate)]?.biweekly         ?? 0,
    totalContributed: map[String(rate)]?.totalContributed ?? 0,
    investmentGain:   map[String(rate)]?.investmentGain   ?? 0,
    catchUpMonthly:   map[String(rate)]?.catchUpMonthly   ?? 0,
    catchUpBiweekly:  map[String(rate)]?.catchUpBiweekly  ?? 0,
  }))
}

function computeCurrentValue(purchaseValue: number, purchaseDate: string, lifeExpectancyYears: number): number {
  const purchased = new Date(purchaseDate)
  if (isNaN(purchased.getTime())) return purchaseValue  // incomplete date string — return original value
  const elapsedDays = Math.max(0, (Date.now() - purchased.getTime()) / 86_400_000)
  const remaining = Math.max(0, 1 - elapsedDays / (lifeExpectancyYears * 365))
  return Math.round(purchaseValue * remaining * 100) / 100
}

function monthsBetween(from: string, to: Date = new Date()): number {
  const start = new Date(from)
  return Math.max(0, (to.getFullYear() - start.getFullYear()) * 12 + to.getMonth() - start.getMonth())
}

export default function CreateAssetForm() {
  const [name, setName] = useState('')
  const [purchaseValue, setPurchaseValue] = useState('')
  const [currentValue, setCurrentValue] = useState('')
  const [currentValueAutoSet, setCurrentValueAutoSet] = useState(false)
  const [accountName, setAccountName] = useState('')
  const [purchaseDate, setPurchaseDate] = useState('')
  const [lifeExpectancy, setLifeExpectancy] = useState('')
  const [status, setStatus] = useState<string | null>(null)

  const [inflationRate, setInflationRate] = useState('0')
  const [inflationAutoSet, setInflationAutoSet] = useState(false)
  const [rows, setRows] = useState<RateRow[] | null>(null)
  const [computing, setComputing] = useState(false)
  const [computeError, setComputeError] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Asset category panel
  const [showCategoryPanel, setShowCategoryPanel] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<{ id: number; name: string; statcan_vector_id: number | null } | null>(null)
  const [fetchingCpi, setFetchingCpi] = useState(false)

  const pv        = parseFloat(purchaseValue)
  const years     = parseInt(lifeExpectancy, 10)
  const inflation = parseFloat(inflationRate) || 0
  const valid     = pv > 0 && years > 0 && !isNaN(pv) && !isNaN(years)

  const today = new Date().toISOString().split('T')[0]

  // Inflation-adjusted replacement cost
  const adjustedTarget = valid ? Math.round(pv * Math.pow(1 + inflation / 100, years) * 100) / 100 : 0

  // Months elapsed since purchase (0 when no purchase date or bought today)
  const elapsedMonths = purchaseDate ? monthsBetween(purchaseDate) : 0
  const totalMonths   = valid ? years * 12 : 0
  const isLateStart   = !!purchaseDate && purchaseDate < today

  // Auto-compute current market value from straight-line depreciation
  useEffect(() => {
    if (!purchaseDate || !valid) return
    if (isNaN(new Date(purchaseDate).getTime())) return  // partial date while typing
    setCurrentValue(String(computeCurrentValue(pv, purchaseDate, years)))
    setCurrentValueAutoSet(true)
  }, [pv, purchaseDate, years, valid])

  // Straight-line depreciation — local, instant
  const dailyDepr   = valid ? pv / (years * 365) : null
  const monthlyDepr = valid ? pv / (years * 12)  : null
  const annualDepr  = valid ? pv / years          : null

  // 0% sinking fund on inflation-adjusted target
  const zeroMonthly   = valid ? adjustedTarget / totalMonths    : null
  const zeroBiweekly  = valid ? adjustedTarget / (years * 26)   : null
  const zeroCatchUp   = isLateStart ? elapsedMonths * (adjustedTarget / totalMonths) : null

  // Planning API — anchored to purchaseDate so the schedule maps to real calendar dates
  useEffect(() => {
    if (!valid) { setRows(null); setComputeError(null); return }
    setRows(null)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setComputing(true)
      setComputeError(null)
      try {
        const startDate = purchaseDate || today
        const results = await simulateScenarios(buildSpecs(adjustedTarget, years, startDate))
        setRows(parseResults(results))
      } catch (err: any) {
        setComputeError(err.message || 'Simulation failed')
        setRows(null)
      } finally {
        setComputing(false)
      }
    }, 600)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [adjustedTarget, years, purchaseDate, valid])

  const handleCategorySelect = async (account: { id: number; name: string; statcan_vector_id: number | null }) => {
    setSelectedCategory(account)
    if (!account.statcan_vector_id) return
    setFetchingCpi(true)
    try {
      const result = await fetchCpiRate(account.statcan_vector_id)
      if (result.cagr_pct !== null) {
        setInflationRate(String(result.cagr_pct))
        setInflationAutoSet(true)
      }
    } catch {
      // leave inflation rate unchanged if StatCan is unreachable
    } finally {
      setFetchingCpi(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus('Saving...')
    try {
      const res = await fetch('/api/assets/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          purchase_value: purchaseValue,
          current_market_value: currentValue,
          purchase_date: purchaseDate || null,
          life_expectancy_years: lifeExpectancy ? parseInt(lifeExpectancy, 10) : null,
          account_name: accountName,
        }),
      })
      if (!res.ok) throw new Error((await res.text()) || 'Failed')
      const data = await res.json()
      setStatus(`Created asset ${data.name} (id=${data.id})`)
      setName(''); setPurchaseValue(''); setCurrentValue(''); setCurrentValueAutoSet(false)
      setAccountName(''); setPurchaseDate(''); setLifeExpectancy('')
      setInflationRate('0'); setInflationAutoSet(false)
      setSelectedCategory(null); setShowCategoryPanel(false); setRows(null)
    } catch (err: any) {
      setStatus(`Error: ${err.message}`)
    }
  }

  return (
    <div className="space-y-6">
      <div className={showCategoryPanel ? 'grid grid-cols-[1fr_280px] gap-4 items-start' : ''}>
      <form onSubmit={handleSubmit} className="p-4 bg-white rounded shadow space-y-3">
        <h3 className="text-lg font-semibold">Create Asset</h3>

        <label className="block text-sm">Name
          <input value={name} onChange={e => setName(e.target.value)} className="mt-1 w-full rounded border px-2 py-1" />
        </label>

        <div className="grid grid-cols-2 gap-2">
          <label className="block text-sm">Purchase value
            <input type="number" value={purchaseValue} onChange={e => setPurchaseValue(e.target.value)} className="mt-1 w-full rounded border px-2 py-1" />
          </label>
          <label className="block text-sm">
            <span className="flex items-center gap-1.5">
              Current market value
              {currentValueAutoSet && (
                <span className="text-xs font-normal text-blue-500 border border-blue-200 bg-blue-50 rounded px-1">computed</span>
              )}
            </span>
            <input
              type="number"
              value={currentValue}
              onChange={e => { setCurrentValue(e.target.value); setCurrentValueAutoSet(false) }}
              className="mt-1 w-full rounded border px-2 py-1"
            />
          </label>
        </div>

        <label className="block text-sm">Purchase date
          <input type="date" value={purchaseDate} onChange={e => setPurchaseDate(e.target.value)} className="mt-1 block w-full rounded border px-2 py-1" />
        </label>

        <label className="block text-sm">Account name (creates an ASSET account)
          <input value={accountName} onChange={e => setAccountName(e.target.value)} className="mt-1 w-full rounded border px-2 py-1" />
        </label>

        <div className="block text-sm">
          <span className="block mb-1">Asset category</span>
          <button
            type="button"
            onClick={() => setShowCategoryPanel(p => !p)}
            className={`w-full text-left rounded border px-2 py-1.5 text-sm transition-colors
              ${showCategoryPanel ? 'border-blue-400 bg-blue-50 text-blue-700' : 'bg-white hover:bg-slate-50 text-slate-700'}
            `}
          >
            {selectedCategory
              ? <span className="flex items-center gap-2">
                  {selectedCategory.name}
                  {selectedCategory.statcan_vector_id && (
                    <span className="text-xs font-normal text-blue-500 border border-blue-200 bg-blue-50 rounded px-1">CPI linked</span>
                  )}
                </span>
              : <span className="text-slate-400">Browse expense categories…</span>
            }
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <label className="block text-sm">Life expectancy (years)
            <input
              type="number" min="1" step="1" value={lifeExpectancy}
              onChange={e => setLifeExpectancy(e.target.value)}
              placeholder="e.g. 15"
              className="mt-1 w-full rounded border px-2 py-1 block"
            />
          </label>
          <label className="block text-sm">
            <span className="flex items-center gap-1.5">
              Inflation assumption (%)
              {fetchingCpi && <span className="text-xs text-gray-400 animate-pulse">fetching…</span>}
              {inflationAutoSet && !fetchingCpi && (
                <span className="text-xs font-normal text-blue-500 border border-blue-200 bg-blue-50 rounded px-1">from StatCan</span>
              )}
            </span>
            <input
              type="number" min="0" step="0.1" value={inflationRate}
              onChange={e => { setInflationRate(e.target.value); setInflationAutoSet(false) }}
              placeholder="e.g. 2"
              className="mt-1 w-full rounded border px-2 py-1 block"
            />
          </label>
        </div>

        <div className="flex items-center gap-3">
          <button className="bg-blue-600 text-white px-3 py-1.5 rounded text-sm" type="submit">Create</button>
          {status && <span className="text-sm text-gray-600">{status}</span>}
        </div>
      </form>

      {showCategoryPanel && (
        <div className="sticky top-4 h-[520px]">
          <ExpenseCategoryPanel
            selectedId={selectedCategory?.id ?? null}
            onSelect={handleCategorySelect}
            onClose={() => setShowCategoryPanel(false)}
          />
        </div>
      )}
      </div>{/* end grid wrapper */}

      {valid && (
        <div className="p-4 bg-white rounded shadow space-y-5">
          <h3 className="text-base font-semibold">Asset Economics</h3>

          {/* Straight-line depreciation */}
          <section>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              Straight-line depreciation — {cad.format(pv)} over {years} yr
            </p>
            <div className="grid grid-cols-3 gap-3 text-center">
              {([['Daily', dailyDepr], ['Monthly', monthlyDepr], ['Annual', annualDepr]] as [string, number][]).map(([label, val]) => (
                <div key={label} className="bg-amber-50 rounded p-2">
                  <p className="text-xs text-gray-500">{label}</p>
                  <p className="font-mono text-sm font-semibold">{cad.format(val)}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Replacement sinking fund — full term */}
          <section>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              Replacement fund — {cad.format(adjustedTarget)} target in {years} yr
              {inflation > 0 && <span className="normal-case font-normal ml-1">({cad.format(pv)} today × {inflation}% inflation → {cad.format(adjustedTarget)})</span>}
              {' '}({totalMonths} monthly payments)
            </p>
            {computing && <p className="text-xs text-gray-400 animate-pulse">Computing via planning API…</p>}
            {computeError && <p className="text-xs text-red-500">{computeError}</p>}

            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b text-xs text-gray-500">
                  <th className="text-left py-1.5 font-medium">Rate</th>
                  <th className="text-right py-1.5 font-medium">Monthly</th>
                  <th className="text-right py-1.5 font-medium">Biweekly</th>
                  <th className="text-right py-1.5 font-medium">You contribute</th>
                  <th className="text-right py-1.5 font-medium">Growth covers</th>
                  {isLateStart && <th className="text-right py-1.5 font-medium text-orange-600">Fund should be at</th>}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b text-gray-700">
                  <td className="py-1.5 text-gray-400">0%</td>
                  <td className="py-1.5 text-right font-mono">{cad.format(zeroMonthly!)}</td>
                  <td className="py-1.5 text-right font-mono">{cad.format(zeroBiweekly!)}</td>
                  <td className="py-1.5 text-right font-mono">{cad.format(pv)}</td>
                  <td className="py-1.5 text-right font-mono text-gray-400">{cad.format(0)}</td>
                  {isLateStart && <td className="py-1.5 text-right font-mono text-orange-600">{cad.format(zeroCatchUp!)}</td>}
                </tr>
                {rows?.map(row => (
                  <tr key={row.rate} className="border-b last:border-0 text-gray-700">
                    <td className="py-1.5">{row.rate}%</td>
                    <td className="py-1.5 text-right font-mono">{cad.format(row.monthly)}</td>
                    <td className="py-1.5 text-right font-mono">{cad.format(row.biweekly)}</td>
                    <td className="py-1.5 text-right font-mono">{cad.format(row.totalContributed)}</td>
                    <td className="py-1.5 text-right font-mono text-green-600">{cad.format(row.investmentGain)}</td>
                    {isLateStart && <td className="py-1.5 text-right font-mono text-orange-600">{cad.format(row.catchUpMonthly)}</td>}
                  </tr>
                ))}
                {computing && !rows && RATES.map(r => (
                  <tr key={r} className="border-b animate-pulse">
                    <td className="py-1.5">{r}%</td>
                    {[0,1,2,3, ...(isLateStart ? [4] : [])].map(i => <td key={i} className="py-1.5 text-right"><span className="inline-block bg-gray-100 rounded w-16 h-4" /></td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

        </div>
      )}
    </div>
  )
}
