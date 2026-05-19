import React from 'react'
import RoomEditor from './RoomEditor'
import type { FloorShape } from './HouseEditor'

const FloorList: React.FC<{
  floors: FloorShape[]
  onUpdate: (id: string, patch: Partial<FloorShape>) => void
  onRemove: (id: string) => void
}> = ({
  floors,
  onUpdate,
  onRemove,
}: {
  floors: FloorShape[]
  onUpdate: (id: string, patch: Partial<FloorShape>) => void
  onRemove: (id: string) => void
}) => {
  return (
    <div className="mt-2 space-y-3">
      {floors.map(f => (
        <div key={f.id} className="border rounded p-2">
          <div className="flex items-center justify-between">
            <div>
              <input
                className="font-medium text-sm mr-2"
                value={f.name}
                onChange={e => onUpdate(f.id, { name: e.target.value })}
              />
              <span className="text-xs text-gray-500">#{f.floorNumber}</span>
            </div>
            <button className="text-red-500 text-sm" onClick={() => onRemove(f.id)}>
              Remove
            </button>
          </div>

          <div className="mt-2">
            <RoomEditor floorId={f.id} />
          </div>
        </div>
      ))}
    </div>
  )
}

export default FloorList
