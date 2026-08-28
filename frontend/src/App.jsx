import { useEffect, useState } from 'react'

function App() {
  const [status, setStatus] = useState('checking backend...')

  useEffect(() => {
    fetch('http://127.0.0.1:8000/health')
      .then((res) => res.json())
      .then((data) => setStatus(`backend says: ${JSON.stringify(data)}`))
      .catch((err) => setStatus(`fetch failed: ${err}`))
  }, [])

  return (
    <div>
      <h1>smoke test</h1>
      <p id="status">{status}</p>
    </div>
  )
}

export default App
