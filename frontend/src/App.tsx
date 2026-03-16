import { useState, useEffect } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import { Button } from "@/components/ui/button"

function App() {
  const [count, setCount] = useState(0)
  const [apiMessage, setApiMessage] = useState('')

  useEffect(() => {
    fetch('http://localhost:8000/api/hello')
      .then(res => res.json())
      .then(data => setApiMessage(data.message))
      .catch(err => console.error(err))
  }, [])

  return (
    <>
      <div>
        <a href="https://vitejs.dev" target="_blank">
          <img src={viteLogo} className="logo" alt="Vite logo" />
        </a>
        <a href="https://react.dev" target="_blank">
          <img src={reactLogo} className="logo react" alt="React logo" />
        </a>
      </div>
      <h1>Django Ninja + React</h1>
      <div className="card text-center flex flex-col items-center gap-4">
        <Button onClick={() => setCount((count) => count + 1)} variant="default">
          count is {count}
        </Button>
        <div style={{ marginTop: '20px', padding: '10px', border: '1px solid #ddd', borderRadius: '8px' }}>
          <strong>Backend API Response:</strong>
          <p>{apiMessage ? apiMessage : 'Loading from http://localhost:8000/api/hello...'}</p>
        </div>
      </div>
      <p className="read-the-docs">
        Click on the Vite and React logos to learn more
      </p>
    </>
  )
}

export default App
