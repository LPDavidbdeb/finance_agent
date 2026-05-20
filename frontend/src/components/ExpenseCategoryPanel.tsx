import React, { useState, useEffect, useMemo } from 'react'
import { ChevronRight, ChevronDown, X } from 'lucide-react'
import { fetchAccountTree } from '../api/client'

interface Account {
  id: number
  name: string
  account_type: string
  statcan_vector_id: number | null
  children: Account[]
}

function matchesFilter(account: Account, q: string): boolean {
  if (!q) return true
  if (account.name.toLowerCase().includes(q)) return true
  return account.children.some(c => matchesFilter(c, q))
}

interface NodeProps {
  account: Account
  depth: number
  selectedId: number | null
  onSelect: (account: Account) => void
  filter: string
}

function ExpenseNode({ account, depth, selectedId, onSelect, filter }: NodeProps) {
  const [open, setOpen] = useState(depth < 2)
  const hasChildren = account.children.length > 0
  const isSelected = account.id === selectedId
  const hasCpi = account.statcan_vector_id !== null

  if (filter && !matchesFilter(account, filter.toLowerCase())) return null

  return (
    <div>
      <div
        className={`flex items-center gap-1 py-1 pr-2 rounded cursor-pointer transition-colors text-sm
          ${isSelected
            ? 'bg-blue-100 text-blue-800 font-semibold'
            : 'hover:bg-slate-100 text-slate-700'}
        `}
        style={{ paddingLeft: `${0.5 + depth * 1.25}rem` }}
        onClick={() => {
          if (hasChildren) setOpen(o => !o)
          if (hasCpi) onSelect(account)
        }}
      >
        <span className="w-4 shrink-0 flex items-center justify-center">
          {hasChildren
            ? open
              ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
            : null}
        </span>

        <span className={`flex-1 truncate ${!hasCpi ? 'text-slate-400' : ''}`}>
          {account.name}
        </span>

        {hasCpi && (
          <span className="shrink-0 w-1.5 h-1.5 rounded-full bg-blue-400" title="CPI inflation data available" />
        )}
      </div>

      {open && hasChildren && (
        <div>
          {account.children.map(child => (
            <ExpenseNode
              key={child.id}
              account={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
              filter={filter}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface PanelProps {
  selectedId: number | null
  onSelect: (account: Account) => void
  onClose: () => void
}

export function ExpenseCategoryPanel({ selectedId, onSelect, onClose }: PanelProps) {
  const [tree, setTree] = useState<Account[]>([])
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAccountTree()
      .then(data => setTree(data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const expenseRoots = useMemo(
    () => tree.filter(a => a.account_type === 'EXPENSE'),
    [tree]
  )

  return (
    <div className="bg-white rounded shadow flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between px-3 pt-3 pb-2 border-b shrink-0">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Expense categories</p>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="px-2 py-1.5 border-b shrink-0">
        <input
          type="search"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter…"
          className="w-full text-xs rounded border px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300"
        />
      </div>

      <div className="overflow-y-auto flex-1 px-1 py-1">
        {loading && (
          <p className="text-xs text-slate-400 text-center py-4">Loading…</p>
        )}
        {!loading && expenseRoots.map(root => (
          <ExpenseNode
            key={root.id}
            account={root}
            depth={0}
            selectedId={selectedId}
            onSelect={onSelect}
            filter={filter}
          />
        ))}
      </div>

      <div className="px-3 py-1.5 border-t shrink-0">
        <p className="text-[10px] text-slate-400">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-400 mr-1 align-middle" />
          CPI data available · grey = no match
        </p>
      </div>
    </div>
  )
}
