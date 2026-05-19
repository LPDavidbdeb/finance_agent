import React, { useState } from 'react'
import FloorList from './FloorList'

export interface FloorShape {
  id: string
  floorNumber: number
  name?: string
}

export interface HouseShape {
  id: string
  name: string
  address?: string
  floors: FloorShape[]
}

const makeId = () => Math.random().toString(36).slice(2, 9)

const HouseEditor: React.FC<{ initial?: Partial<HouseShape> }> = ({ initial }) => {
  const [house, setHouse] = useState<HouseShape>(() => ({
    id: initial?.id || makeId(),
    name: initial?.name || 'New House',
    address: initial?.address || '',
    floors: initial?.floors || [],
  }))

  const addFloor = () => {
    const next = {
      id: makeId(),
      floorNumber: house.floors.length + 1,
      name: `Floor ${house.floors.length + 1}`,
    }
    setHouse({ ...house, floors: [...house.floors, next] })
  }

  const updateFloor = (id: string, patch: Partial<FloorShape>) => {
    setHouse({
      ...house,
      floors: house.floors.map(f => (f.id === id ? { ...f, ...patch } : f)),
    })
  }

  const removeFloor = (id: string) => {
    setHouse({ ...house, floors: house.floors.filter(f => f.id !== id) })
  }

  return (
    <div className="p-4 bg-white rounded shadow">
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700">House name</label>
        <input
          className="mt-1 block w-full rounded border px-2 py-1"
          value={house.name}
          onChange={e => setHouse({ ...house, name: e.target.value })}
        />
        <label className="block text-sm font-medium text-gray-700 mt-2">Address</label>
        <input
          className="mt-1 block w-full rounded border px-2 py-1"
          value={house.address}
          onChange={e => setHouse({ ...house, address: e.target.value })}
        />
      </div>

      <div className="mb-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Floors</h3>
          <button className="text-sm text-blue-600" onClick={addFloor}>
            + Add floor
          </button>
        </div>
        <FloorList floors={house.floors} onUpdate={updateFloor} onRemove={removeFloor} />
      </div>
    </div>
  )
}

export default HouseEditor
