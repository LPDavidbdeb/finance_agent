import React, { useState } from 'react'

export default function CreateAssetForm() {
  const [name, setName] = useState('')
  const [purchaseValue, setPurchaseValue] = useState('')
  const [currentValue, setCurrentValue] = useState('')
  const [accountName, setAccountName] = useState('')
  const [purchaseDate, setPurchaseDate] = useState('')
  const [lifeExpectancy, setLifeExpectancy] = useState('')
  const [status, setStatus] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus('Saving...')

    try {
      const res = await fetch('/api/assets/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          purchase_value: purchaseValue,
          current_market_value: currentValue,
          purchase_date: purchaseDate || null,
          life_expectancy_years: lifeExpectancy ? parseInt(lifeExpectancy, 10) : null,
          account_name: accountName,
        }),
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || 'Failed')
      }

      const data = await res.json()
      setStatus(`Created asset ${data.name} (id=${data.id})`)
      setName('')
      setPurchaseValue('')
      setCurrentValue('')
      setAccountName('')
      setPurchaseDate('')
      setLifeExpectancy('')
    } catch (err: any) {
      setStatus(`Error: ${err.message}`)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="p-4 bg-white rounded shadow">
      <h3 className="text-lg font-semibold mb-2">Create Asset</h3>

      <label className="block text-sm">Name</label>
      <input value={name} onChange={e => setName(e.target.value)} className="w-full rounded border px-2 py-1 mb-2" />

      <div className="grid grid-cols-2 gap-2">
        <label className="block text-sm">Purchase value
          <input type="number" value={purchaseValue} onChange={e => setPurchaseValue(e.target.value)} className="w-full rounded border px-2 py-1" />
        </label>
        <label className="block text-sm">Current market value
          <input type="number" value={currentValue} onChange={e => setCurrentValue(e.target.value)} className="w-full rounded border px-2 py-1" />
        </label>
      </div>

      <label className="block text-sm mt-2">Account name (will create an ASSET account)</label>
       <label className="block text-sm mt-2">Purchase date</label>
       <input
         type="date"
         value={purchaseDate}
         onChange={e => setPurchaseDate(e.target.value)}
         className="mt-1 block w-full rounded border px-2 py-1 mb-2"
       />
      <input value={accountName} onChange={e => setAccountName(e.target.value)} className="w-full rounded border px-2 py-1 mb-2" />

      <label className="block text-sm mt-2">Life expectancy (years)</label>
      <input
        type="number"
        min="0"
        step="1"
        value={lifeExpectancy}
        onChange={e => setLifeExpectancy(e.target.value)}
        placeholder="e.g. 10"
        className="mt-1 block w-40 rounded border px-2 py-1 mb-2"
      />

      <div className="flex items-center gap-2">
        <button className="bg-blue-600 text-white px-3 py-1 rounded" type="submit">Create</button>
        {status && <div className="text-sm text-gray-700">{status}</div>}
      </div>
    </form>
  )
}
