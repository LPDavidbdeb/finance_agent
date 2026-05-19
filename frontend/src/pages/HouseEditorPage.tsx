import React from 'react'
import HouseEditor from '../components/HouseEditor'

const HouseEditorPage: React.FC = () => {
  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-2xl font-bold mb-4">House Editor (Prototype)</h1>
        <HouseEditor />
      </div>
    </div>
  )
}

export default HouseEditorPage
