import { useState, useEffect, useRef } from 'react'
import { simulateScenarios, type ScenarioSpec, type ScenarioResult, type PeriodRow } from '../api/client'

const RATES = [3, 5, 7] as const
const FREQS = ['MONTHLY', 'BIWEEKLY'] as const

export interface RateRow {
  rate: number
  monthly: number
  biweekly: number
  totalContributed: number
  investmentGain: number
  catchUpMonthly: number
  catchUpBiweekly: number
}

function balanceAsOfToday(schedule: PeriodRow[]): number {
  const today = new Date().toISOString().split('T')[0]
  let balance = 0
  for (const row of schedule) {
    if (row.payment_date <= today) balance = row.balance_after
    else break
  }
  return balance
}

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

interface SimulationState {
  rows: RateRow[] | null
  computing: boolean
  error: string | null
}

export function useSinkingFundSimulation(
  adjustedTarget: number,
  years: number,
  startDate: string,
  enabled: boolean,
): SimulationState {
  const [rows, setRows] = useState<RateRow[] | null>(null)
  const [computing, setComputing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!enabled) { setRows(null); setError(null); return }
    setRows(null)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setComputing(true)
      setError(null)
      try {
        const results = await simulateScenarios(buildSpecs(adjustedTarget, years, startDate))
        setRows(parseResults(results))
      } catch (err: any) {
        setError(err.message || 'Simulation failed')
        setRows(null)
      } finally {
        setComputing(false)
      }
    }, 600)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [adjustedTarget, years, startDate, enabled])

  return { rows, computing, error }
}

export { RATES }
