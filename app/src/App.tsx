import { useEffect, useState } from 'react'

function App() {
  const [health, setHealth] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('http://127.0.0.1:8000/health')
      .then((res) => {
        if (!res.ok) throw new Error('Network response was not ok')
        return res.json()
      })
      .then((data) => setHealth(data.status))
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div style={{ textAlign: 'center', marginTop: '2rem' }}>
      <h1>Backend Health Check</h1>
      {health && <p>Status: <b>{health}</b></p>}
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {!health && !error && <p>Checking health...</p>}
    </div>
  )
}

export default App
