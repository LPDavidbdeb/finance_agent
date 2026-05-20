import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Trash2, Calendar, Target, ChevronRight } from 'lucide-react'
import {
  fetchProjects, createProject, deleteProject,
  SinkingFundProjectList, ProjectIn,
} from '../api/client'

const fmt = (n: number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(n)

function yearsMonthsUntil(targetDate: string): string {
  const now = new Date()
  const target = new Date(targetDate)
  const totalMonths =
    (target.getFullYear() - now.getFullYear()) * 12 + (target.getMonth() - now.getMonth())
  if (totalMonths <= 0) return 'past'
  const years = Math.floor(totalMonths / 12)
  const months = totalMonths % 12
  if (years === 0) return `${months}mo`
  if (months === 0) return `${years}yr`
  return `${years}yr ${months}mo`
}

const EMPTY_FORM: ProjectIn = {
  name: '',
  target_date: '',
  savings_start_date: null,
  notes: '',
}

export function ProjectsPage() {
  const [projects, setProjects] = useState<SinkingFundProjectList[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<ProjectIn>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState<number | null>(null)

  useEffect(() => {
    fetchProjects()
      .then(setProjects)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      await createProject({
        ...form,
        savings_start_date: form.savings_start_date || null,
      })
      const updated = await fetchProjects()
      setProjects(updated)
      setForm(EMPTY_FORM)
      setShowForm(false)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm('Delete this project and all its line items?')) return
    setDeleting(id)
    try {
      await deleteProject(id)
      setProjects(prev => prev.filter(p => p.id !== id))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Savings Projects</h1>
          <p className="text-sm text-slate-500 mt-0.5">Future spending goals — group cash flows by project and track sinking fund targets.</p>
        </div>
        <button
          onClick={() => setShowForm(v => !v)}
          className="flex items-center gap-1.5 bg-blue-600 text-white px-3 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Project
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-md">
          {error}
        </div>
      )}

      {showForm && (
        <div className="bg-white rounded-lg border border-blue-200 shadow-sm p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">New Project</h2>
          <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-600 mb-1">Project name</label>
              <input
                required
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                placeholder="e.g. Tokyo trip 2028, Kitchen renovation"
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
              <label className="block text-xs font-medium text-slate-600 mb-1">Savings start date <span className="text-slate-400">(optional — defaults to today)</span></label>
              <input
                type="date"
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.savings_start_date || ''}
                onChange={e => setForm(f => ({ ...f, savings_start_date: e.target.value || null }))}
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-600 mb-1">Notes</label>
              <textarea
                rows={2}
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                placeholder="Optional context…"
                value={form.notes}
                onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
              />
            </div>
            <div className="col-span-2 flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => { setShowForm(false); setForm(EMPTY_FORM) }}
                className="px-4 py-2 text-sm text-slate-600 border rounded-md hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {saving ? 'Creating…' : 'Create Project'}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading && (
        <p className="text-sm text-slate-400 text-center py-12">Loading projects…</p>
      )}

      {!loading && projects.length === 0 && (
        <div className="text-center py-16 text-slate-400">
          <Target className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No projects yet. Create one to start planning your future spending.</p>
        </div>
      )}

      {!loading && projects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map(p => {
            const countdown = yearsMonthsUntil(p.target_date)
            const isPast = countdown === 'past'
            return (
              <div key={p.id} className="bg-white rounded-lg border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
                <Link to={`/projects/${p.id}`} className="block p-5">
                  <div className="flex items-start justify-between">
                    <h3 className="font-semibold text-slate-900 text-base leading-tight">{p.name}</h3>
                    <span className={`ml-2 shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${
                      isPast
                        ? 'bg-red-100 text-red-600'
                        : 'bg-blue-100 text-blue-700'
                    }`}>
                      {countdown}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center gap-1 text-xs text-slate-500">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>{new Date(p.target_date).toLocaleDateString('en-CA', { year: 'numeric', month: 'short', day: 'numeric' })}</span>
                  </div>
                  <div className="mt-3 flex items-center justify-between">
                    <span className="text-xs text-slate-400">
                      {p.line_item_count === 0 ? 'No items yet' : `${p.line_item_count} item${p.line_item_count !== 1 ? 's' : ''}`}
                    </span>
                    <ChevronRight className="w-4 h-4 text-slate-300" />
                  </div>
                </Link>
                <div className="border-t px-5 py-2 flex justify-end">
                  <button
                    onClick={() => handleDelete(p.id)}
                    disabled={deleting === p.id}
                    className="text-slate-400 hover:text-red-500 transition-colors disabled:opacity-30"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
