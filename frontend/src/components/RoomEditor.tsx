import React, { useState } from 'react'
import WindowEditor from './WindowEditor'

const RoomEditor: React.FC<{ floorId: string }> = ({ floorId }) => {
  const [rooms, setRooms] = useState<Array<any>>([])

  const addRoom = () => {
    setRooms([...rooms, { id: Math.random().toString(36).slice(2, 9), name: 'New Room', length: 3, width: 3, height: 2.5, windows: [] }])
  }

  const updateRoom = (id: string, patch: Partial<any>) => {
    setRooms(rooms.map(r => (r.id === id ? { ...r, ...patch } : r)))
  }

  const removeRoom = (id: string) => {
    setRooms(rooms.filter(r => r.id !== id))
  }

  return (
    <div data-floor-id={floorId}>
      <div className="flex items-center justify-between">
        <h4 className="font-medium">Rooms</h4>
        <button className="text-sm text-blue-600" onClick={addRoom}>+ Add room</button>
      </div>

      <div className="mt-2 space-y-2">
        {rooms.map(r => (
          <div key={r.id} className="border rounded p-2">
            <div className="flex items-center justify-between">
              <input value={r.name} onChange={e => updateRoom(r.id, { name: e.target.value })} className="mr-2" />
              <button className="text-red-500 text-sm" onClick={() => removeRoom(r.id)}>Remove</button>
            </div>

            <div className="grid grid-cols-3 gap-2 mt-2">
              <label className="text-xs">Length (m)
                <input type="number" value={r.length} onChange={e => updateRoom(r.id, { length: parseFloat(e.target.value) })} className="block w-full rounded border px-1" />
              </label>
              <label className="text-xs">Width (m)
                <input type="number" value={r.width} onChange={e => updateRoom(r.id, { width: parseFloat(e.target.value) })} className="block w-full rounded border px-1" />
              </label>
              <label className="text-xs">Height (m)
                <input type="number" value={r.height} onChange={e => updateRoom(r.id, { height: parseFloat(e.target.value) })} className="block w-full rounded border px-1" />
              </label>
            </div>

            <div className="mt-2">
              <WindowEditor roomId={r.id} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default RoomEditor
