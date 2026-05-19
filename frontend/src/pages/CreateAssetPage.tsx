import React from 'react'
import CreateAssetForm from '../components/CreateAssetForm'

const CreateAssetPage: React.FC = () => {
  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-2xl font-bold mb-4">Create Asset</h1>
        <CreateAssetForm />
      </div>
    </div>
  )
}

export default CreateAssetPage
