import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Plus, Trash2, Pencil, Check, X, TrendingUp, Calendar, Loader2, Target } from 'lucide-react'
import {
  fetchProject, updateProject, addLineItem, updateLineItem, deleteLineItem, fetchCpiRate,
  SinkingFundProject, SinkingFundLineItem, LineItemIn,
} from '../api/client'
import { ExpenseCategoryPanel } from '../components/ExpenseCategoryPanel'

// ── Math helpers ──────────────────────────────────────────────────────────────

function monthsBetween(from: Date, to: Date): number {
  return Math.max(
    0,
    (to.getFullYear() - from.getFullYear()) * 12 + (to.getMonth() - from.getMonth()),
  )
}

function futureValue(todayTotal: number, inflationPct: number, years: number): number {
  return todayTotal * Math.pow(1 + inflationPct / 100, years)
}

// Sinking fund PMT at 0% assumed return (conservative — just divide evenly)
function monthlyPMT(fv: number, months: number): number {
  if (months <= 0) return fv
  return fv / months
}

function yearsUntil(targetDate: string): number {
  const now = new Date()
  const target = new Date(targetDate)
  return (target.getTime() - now.getTime()) / (365.25 * 24 * 3600 * 1000)
}

const fmt = (n: number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(n)

const fmtPrecise = (n: number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 2 }).format(n)

// ── CPI rate cache per vector_id ──────────────────────────────────────────────

type CpiCache = Record<number, number | null>

// ── Line item row display ─────────────────────────────────────────────────────

interface ItemRowProps {
  item: SinkingFundLineItem
  targetDate: string
  savingsStartDate: string | null
  cpiCache: CpiCache
  onEdit: (item: SinkingFundLineItem) => void
  onDelete: (id: number) => void
  deleting: boolean
}

function ItemRow({ item, targetDate, savingsStartDate, cpiCache, onEdit, onDelete, deleting }: ItemRowProps) {
  const start = savingsStartDate ? new Date(savingsStartDate) : new Date()
  const months = monthsBetween(start, new Date(targetDate))
  const years = yearsUntil(targetDate)

  const effectiveInflation: number | null =
    item.inflation_rate_override !== null
      ? Number(item.inflation_rate_override)
      : item.statcan_vector_id !== null
      ? cpiCache[item.statcan_vector_id] ?? null
      : 2.0

  const todayTotal = Number(item.total_today_price)
  const fv = effectiveInflation !== null ? futureValue(todayTotal, effectiveInflation, Math.max(0, years)) : null
  const pmt = fv !== null ? monthlyPMT(fv, months) : null

  const inflationLabel =
    item.inflation_rate_override !== null
      ? `${Number(item.inflation_rate_override).toFixed(1)}% (manual)`
      : item.statcan_vector_id !== null
      ? effectiveInflation !== null
        ? `${effectiveInflation.toFixed(1)}% (StatCan)`
        : 'loading…'
      : '2.0% (default)'

  return (
    <tr className="border-t border-slate-100 hover:bg-slate-50 transition-colors">
      <td className="py-3 px-4">
        <div className="font-medium text-slate-800 text-sm">{item.description}</div>
        {item.expense_category_name && (
          <div className="text-xs text-slate-400 mt-0.5">{item.expense_category_name}</div>
        )}
        {item.source_asset_name && (
          <div className="text-xs text-blue-500 mt-0.5">absorbs: {item.source_asset_name}</div>
        )}
      </td>
      <td className="py-3 px-4 text-right text-sm text-slate-700">
        {fmtPrecise(Number(item.today_price))} × {Number(item.quantity)}
      </td>
      <td className="py-3 px-4 text-right text-sm font-medium text-slate-800">{fmt(todayTotal)}</td>
      <td className="py-3 px-4 text-right text-xs text-slate-500">{inflationLabel}</td>
      <td className="py-3 px-4 text-right text-sm font-semibold text-slate-900">
        {fv !== null ? fmt(fv) : '—'}
      </td>
      <td className="py-3 px-4 text-right text-sm font-semibold text-blue-700">
        {pmt !== null ? `${fmt(pmt)}/mo` : '—'}
      </td>
      <td className="py-3 px-4 text-right">
        <div className="flex items-center justify-end gap-2">
          <button onClick={() => onEdit(item)} className="text-slate-400 hover:text-blue-600 transition-colors">
            <Pencil className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onDelete(item.id)}
            disabled={deleting}
            className="text-slate-400 hover:text-red-500 transition-colors disabled:opacity-30"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </td>
    </tr>
  )
}

// ── Line item form ────────────────────────────────────────────────────────────

interface LineItemFormState {
  description: string
  today_price: string
  quantity: string
  inflation_rate_override: string
  expense_category_id: number | null
  expense_category_name: string | null
  statcan_vector_id: number | null
}

const EMPTY_ITEM: LineItemFormState = {
  description: '',
  today_price: '',
  quantity: '1',
  inflation_rate_override: '',
  expense_category_id: null,
  expense_category_name: null,
  statcan_vector_id: null,
}

interface LineItemFormProps {
  initial?: LineItemFormState
  onSave: (data: LineItemIn) => Promise<void>
  onCancel: () => void
}

function LineItemForm({ initial = EMPTY_ITEM, onSave, onCancel }: LineItemFormProps) {
  const [form, setForm] = useState<LineItemFormState>(initial)
  const [showCategoryPanel, setShowCategoryPanel] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await onSave({
        description: form.description,
        today_price: parseFloat(form.today_price),
        quantity: parseFloat(form.quantity) || 1,
        expense_category_id: form.expense_category_id,
        inflation_rate_override: form.inflation_rate_override ? parseFloat(form.inflation_rate_override) : null,
        source_asset_id: null,
      })
    } catch (e: any) {
      setError(e.message)
      setSaving(false)
    }
  }

  function handleCategorySelect(account: { id: number; name: string; statcan_vector_id: number | null }) {
    setForm(f => ({
      ...f,
      expense_category_id: account.id,
      expense_category_name: account.name,
      statcan_vector_id: account.statcan_vector_id,
    }))
    setShowCategoryPanel(false)
  }

  return (
    <form onSubmit={handleSubmit} className="bg-blue-50 rounded-lg p-4 border border-blue-200">
      {error && <p className="text-xs text-red-600 mb-3">{error}</p>}
      <div className={`grid gap-3 ${showCategoryPanel ? 'grid-cols-[1fr_260px]' : 'grid-cols-1'}`}>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Description</label>
            <input
              required
              className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              placeholder="e.g. Return flights YUL–NRT"
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Unit price (today's $)</label>
              <input
                required
                type="number"
                min="0"
                step="0.01"
                className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                placeholder="0.00"
                value={form.today_price}
                onChange={e => setForm(f => ({ ...f, today_price: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Quantity</label>
              <input
                type="number"
                min="1"
                step="1"
                className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.quantity}
                onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Expense category</label>
              <button
                type="button"
                onClick={() => setShowCategoryPanel(v => !v)}
                className={`w-full text-left border rounded px-3 py-1.5 text-sm transition-colors ${
                  form.expense_category_name
                    ? 'border-blue-300 bg-blue-50 text-blue-800'
                    : 'text-slate-400 hover:bg-slate-50'
                }`}
              >
                {form.expense_category_name || 'Browse categories…'}
              </button>
              {form.statcan_vector_id && (
                <p className="text-[10px] text-blue-500 mt-0.5">CPI linked — inflation auto-filled if no override</p>
              )}
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Inflation % override
                <span className="ml-1 text-slate-400 font-normal">(optional — uses StatCan or 2% default)</span>
              </label>
              <input
                type="number"
                min="0"
                max="30"
                step="0.1"
                className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                placeholder="e.g. 3.5"
                value={form.inflation_rate_override}
                onChange={e => setForm(f => ({ ...f, inflation_rate_override: e.target.value }))}
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end pt-1">
            <button
              type="button"
              onClick={onCancel}
              className="px-3 py-1.5 text-sm text-slate-600 border rounded hover:bg-white transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
        {showCategoryPanel && (
          <div className="h-72">
            <ExpenseCategoryPanel
              selectedId={form.expense_category_id}
              onSelect={handleCategorySelect}
              onClose={() => setShowCategoryPanel(false)}
            />
          </div>
        )}
      </div>
    </form>
  )
}

// ── Project header edit form ──────────────────────────────────────────────────

interface HeaderEditProps {
  project: SinkingFundProject
  onSave: (data: { name: string; target_date: string; savings_start_date: string | null; notes: string }) => Promise<void>
  onCancel: () => void
}

function HeaderEditForm({ project, onSave, onCancel }: HeaderEditProps) {
  const [form, setForm] = useState({
    name: project.name,
    target_date: project.target_date,
    savings_start_date: project.savings_start_date || '',
    notes: project.notes,
  })
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      await onSave({
        name: form.name,
        target_date: form.target_date,
        savings_start_date: form.savings_start_date || null,
        notes: form.notes,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-blue-200 p-5 shadow-sm space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <label className="block text-xs font-medium text-slate-600 mb-1">Project name</label>
          <input
            required
            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Target date</label>
          <input
            required
            type="date"
            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            value={form.target_date}
            onChange={e => setForm(f => ({ ...f, target_date: e.target.value }))}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Savings start date</label>
          <input
            type="date"
            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            value={form.savings_start_date}
            onChange={e => setForm(f => ({ ...f, savings_start_date: e.target.value }))}
          />
        </div>
        <div className="col-span-2">
          <label className="block text-xs font-medium text-slate-600 mb-1">Notes</label>
          <textarea
            rows={2}
            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            value={form.notes}
            onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
          />
        </div>
      </div>
      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel} className="px-3 py-1.5 text-sm border rounded hover:bg-slate-50 transition-colors">Cancel</button>
        <button type="submit" disabled={saving} className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 transition-colors">
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </form>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const projectId = parseInt(id!)

  const [project, setProject] = useState<SinkingFundProject | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingItem, setEditingItem] = useState<SinkingFundLineItem | null>(null)
  const [deletingItem, setDeletingItem] = useState<number | null>(null)
  const [cpiCache, setCpiCache] = useState<CpiCache>({})

  const load = useCallback(async () => {
    try {
      const p = await fetchProject(projectId)
      setProject(p)
      return p
    } catch (e: any) {
      setError(e.message)
      return null
    }
  }, [projectId])

  useEffect(() => {
    load().finally(() => setLoading(false))
  }, [load])

  // Fetch CPI rates for items that need them
  useEffect(() => {
    if (!project) return
    const vectorIds = project.line_items
      .filter(i => i.statcan_vector_id !== null && i.inflation_rate_override === null)
      .map(i => i.statcan_vector_id!)
      .filter(id => !(id in cpiCache))

    if (vectorIds.length === 0) return

    const newCache = { ...cpiCache }
    vectorIds.forEach(id => { newCache[id] = null }) // mark as loading
    setCpiCache(newCache)

    vectorIds.forEach(vectorId => {
      fetchCpiRate(vectorId)
        .then(r => setCpiCache(prev => ({ ...prev, [vectorId]: r.cagr_pct })))
        .catch(() => setCpiCache(prev => ({ ...prev, [vectorId]: 2.0 })))
    })
  }, [project])

  async function handleUpdateProject(data: { name: string; target_date: string; savings_start_date: string | null; notes: string }) {
    const updated = await updateProject(projectId, data)
    setProject(updated)
    setEditing(false)
  }

  async function handleAddItem(data: LineItemIn) {
    const updated = await addLineItem(projectId, data)
    setProject(updated)
    setShowAddForm(false)
  }

  async function handleUpdateItem(data: LineItemIn) {
    if (!editingItem) return
    const updated = await updateLineItem(projectId, editingItem.id, data)
    setProject(updated)
    setEditingItem(null)
  }

  async function handleDeleteItem(itemId: number) {
    if (!window.confirm('Remove this line item?')) return
    setDeletingItem(itemId)
    try {
      const updated = await deleteLineItem(projectId, itemId)
      setProject(updated)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setDeletingItem(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    )
  }

  if (error || !project) {
    return (
      <div className="text-center py-16">
        <p className="text-red-600 text-sm">{error || 'Project not found'}</p>
        <Link to="/projects" className="text-blue-600 text-sm mt-2 inline-block hover:underline">← Back to projects</Link>
      </div>
    )
  }

  // Aggregate economics
  const start = project.savings_start_date ? new Date(project.savings_start_date) : new Date()
  const months = monthsBetween(start, new Date(project.target_date))
  const years = yearsUntil(project.target_date)

  let totalToday = 0
  let totalFV = 0
  let totalPMT = 0
  let allResolved = true

  for (const item of project.line_items) {
    const todayTotal = Number(item.total_today_price)
    totalToday += todayTotal

    const inflation: number | null =
      item.inflation_rate_override !== null
        ? Number(item.inflation_rate_override)
        : item.statcan_vector_id !== null
        ? cpiCache[item.statcan_vector_id] ?? null
        : 2.0

    if (inflation === null) {
      allResolved = false
      continue
    }

    const fv = futureValue(todayTotal, inflation, Math.max(0, years))
    totalFV += fv
    totalPMT += monthlyPMT(fv, months)
  }

  const isPast = months <= 0

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link to="/projects" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        All projects
      </Link>

      {/* Project header */}
      {editing ? (
        <HeaderEditForm project={project} onSave={handleUpdateProject} onCancel={() => setEditing(false)} />
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-5">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-900">{project.name}</h1>
              <div className="flex items-center gap-4 mt-2 text-sm text-slate-500">
                <span className="flex items-center gap-1">
                  <Target className="w-3.5 h-3.5" />
                  {new Date(project.target_date).toLocaleDateString('en-CA', { year: 'numeric', month: 'long', day: 'numeric' })}
                </span>
                {project.savings_start_date && (
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" />
                    saving since {new Date(project.savings_start_date).toLocaleDateString('en-CA', { year: 'numeric', month: 'short' })}
                  </span>
                )}
                {!isPast && (
                  <span className={`font-medium ${months < 12 ? 'text-amber-600' : 'text-blue-600'}`}>
                    {months} months away
                  </span>
                )}
                {isPast && <span className="text-red-500 font-medium">Past target date</span>}
              </div>
              {project.notes && <p className="mt-2 text-sm text-slate-600 italic">{project.notes}</p>}
            </div>
            <button
              onClick={() => setEditing(true)}
              className="text-slate-400 hover:text-blue-600 transition-colors"
            >
              <Pencil className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Economics summary */}
      {project.line_items.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Total today's cost</p>
            <p className="text-2xl font-bold text-slate-900 mt-1">{fmt(totalToday)}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Future cost (inflation-adjusted)</p>
            <p className="text-2xl font-bold text-slate-900 mt-1">
              {allResolved ? fmt(totalFV) : <span className="text-base text-slate-400">computing…</span>}
            </p>
            {allResolved && totalFV > totalToday && (
              <p className="text-xs text-slate-400 mt-0.5">+{fmt(totalFV - totalToday)} vs today</p>
            )}
          </div>
          <div className="bg-blue-600 rounded-lg p-4 text-white">
            <p className="text-xs opacity-80 uppercase tracking-wide font-medium">Monthly contribution needed</p>
            <p className="text-2xl font-bold mt-1">
              {allResolved ? `${fmt(totalPMT)}/mo` : <span className="text-base opacity-60">computing…</span>}
            </p>
            {!isPast && months > 0 && (
              <p className="text-xs opacity-70 mt-0.5">over {months} months at 0% return</p>
            )}
          </div>
        </div>
      )}

      {/* Line items */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-800">Line items</h2>
          {!showAddForm && editingItem === null && (
            <button
              onClick={() => setShowAddForm(true)}
              className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800 transition-colors font-medium"
            >
              <Plus className="w-4 h-4" />
              Add item
            </button>
          )}
        </div>

        {showAddForm && (
          <div className="p-4 border-b border-slate-100">
            <LineItemForm
              onSave={handleAddItem}
              onCancel={() => setShowAddForm(false)}
            />
          </div>
        )}

        {project.line_items.length === 0 && !showAddForm && (
          <div className="text-center py-12 text-slate-400 text-sm">
            <TrendingUp className="w-8 h-8 mx-auto mb-2 opacity-30" />
            No items yet. Add line items to start computing sinking fund targets.
          </div>
        )}

        {project.line_items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs font-medium text-slate-500 uppercase tracking-wide bg-slate-50">
                  <th className="py-2.5 px-4 text-left">Item</th>
                  <th className="py-2.5 px-4 text-right">Price × Qty</th>
                  <th className="py-2.5 px-4 text-right">Today's total</th>
                  <th className="py-2.5 px-4 text-right">Inflation</th>
                  <th className="py-2.5 px-4 text-right">Future value</th>
                  <th className="py-2.5 px-4 text-right">Monthly PMT</th>
                  <th className="py-2.5 px-4 text-right"></th>
                </tr>
              </thead>
              <tbody>
                {project.line_items.map(item =>
                  editingItem?.id === item.id ? (
                    <tr key={item.id} className="border-t border-slate-100">
                      <td colSpan={7} className="p-4">
                        <LineItemForm
                          initial={{
                            description: item.description,
                            today_price: String(item.today_price),
                            quantity: String(item.quantity),
                            inflation_rate_override: item.inflation_rate_override !== null ? String(item.inflation_rate_override) : '',
                            expense_category_id: item.expense_category_id,
                            expense_category_name: item.expense_category_name,
                            statcan_vector_id: item.statcan_vector_id,
                          }}
                          onSave={handleUpdateItem}
                          onCancel={() => setEditingItem(null)}
                        />
                      </td>
                    </tr>
                  ) : (
                    <ItemRow
                      key={item.id}
                      item={item}
                      targetDate={project.target_date}
                      savingsStartDate={project.savings_start_date}
                      cpiCache={cpiCache}
                      onEdit={setEditingItem}
                      onDelete={handleDeleteItem}
                      deleting={deletingItem === item.id}
                    />
                  )
                )}
              </tbody>
              {project.line_items.length > 1 && (
                <tfoot className="border-t-2 border-slate-200 bg-slate-50">
                  <tr>
                    <td className="py-3 px-4 text-sm font-semibold text-slate-700" colSpan={2}>Total</td>
                    <td className="py-3 px-4 text-right text-sm font-bold text-slate-900">{fmt(totalToday)}</td>
                    <td className="py-3 px-4"></td>
                    <td className="py-3 px-4 text-right text-sm font-bold text-slate-900">
                      {allResolved ? fmt(totalFV) : '—'}
                    </td>
                    <td className="py-3 px-4 text-right text-sm font-bold text-blue-700">
                      {allResolved ? `${fmt(totalPMT)}/mo` : '—'}
                    </td>
                    <td></td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
      </div>

      <p className="text-xs text-slate-400 text-center">
        Monthly contribution assumes 0% investment return on accumulated savings (conservative). Inflation rates sourced from StatCan CPI table 18100004 where available.
      </p>
    </div>
  )
}
