import React, { useState } from 'react'

const WindowEditor: React.FC<{ roomId: string }> = ({ roomId }) => {
  const [windows, setWindows] = useState<Array<any>>([])

  const addWindow = () => {
    setWindows([...windows, { id: Math.random().toString(36).slice(2, 9), height: 1.2, width: 1.5, quantity: 1 }])
  }

  const updateWindow = (id: string, patch: Partial<any>) => {
    setWindows(windows.map(w => (w.id === id ? { ...w, ...patch } : w)))
  }

  const removeWindow = (id: string) => setWindows(windows.filter(w => w.id !== id))

  return (
    <div data-room-id={roomId}>
      <div className="flex items-center justify-between">
        <h5 className="font-medium">Windows</h5>
        <button className="text-sm text-blue-600" onClick={addWindow}>+ Add window</button>
      </div>

      <div className="mt-2 space-y-2">
        {windows.map(w => (
          <div key={w.id} className="flex items-center gap-2">
            <input type="number" value={w.width} onChange={e => updateWindow(w.id, { width: parseFloat(e.target.value) })} className="w-20 rounded border px-1" />
            <input type="number" value={w.height} onChange={e => updateWindow(w.id, { height: parseFloat(e.target.value) })} className="w-20 rounded border px-1" />
            <input type="number" value={w.quantity} onChange={e => updateWindow(w.id, { quantity: parseInt(e.target.value) })} className="w-20 rounded border px-1" />
            <button className="text-red-500 text-sm" onClick={() => removeWindow(w.id)}>Remove</button>
          </div>
        ))}
      </div>
    </div>
  )
}

export default WindowEditor
