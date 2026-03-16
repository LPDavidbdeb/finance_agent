import { useState } from 'react'
import reactLogo from './assets/react.svg'
import './App.css'
import { Button } from "@/components/ui/button"
import { AccountTree } from './components/AccountTree'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 p-8 flex flex-col items-center font-sans">
      <div className="flex justify-center mb-6">
        <a href="https://react.dev" target="_blank" rel="noreferrer">
          <img src={reactLogo} className="logo react w-24 h-24" alt="React logo" />
        </a>
      </div>
      <h1 className="text-4xl font-bold mb-8 text-center text-slate-800 dark:text-white">Django + React Finance</h1>
      
      <div className="flex flex-col items-center gap-8 w-full">
        <div className="card text-center flex flex-col items-center gap-4 bg-white dark:bg-slate-900 p-6 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800">
          <Button onClick={() => setCount((count) => count + 1)} variant="default">
            Button Clicks: {count}
          </Button>
        </div>

        {/* The new recursive MPTT Account Ledger */}
        <div className="w-full">
          <AccountTree />
        </div>
      </div>
    </div>
  )
}

export default App;