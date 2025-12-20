import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import Chart from 'chart.js/auto'
import './style.css'

function App() {
  const [userId, setUserId] = useState('user-1')
  const [warrantyId, setWarrantyId] = useState('')
  const [status, setStatus] = useState('')
  const [warranty, setWarranty] = useState(null)
  const [summary, setSummary] = useState('')
  const [nudges, setNudges] = useState([])
  const [predictive, setPredictive] = useState(null)
  const [chartRef, setChartRef] = useState(null)

  const headers = {}

  const load = async () => {
    if (!warrantyId) {
      setStatus('Enter warranty id')
      return
    }
    setStatus('Loading...')
    try {
      const w = await fetch(`/warranties/${warrantyId}`, { headers }).then(r => r.json())
      setWarranty(w)
      const sum = await fetch('/warranties/summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...headers },
        body: JSON.stringify({ warranty_id: warrantyId })
      }).then(r => r.json())
      setSummary(sum.summary || '')
      const adv = await fetch(`/advisories/${warrantyId}?user_id=${userId}`, { headers }).then(r => r.json())
      setNudges(adv.nudges || [])
      const pred = await fetch('/predictive/score', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...headers },
        body: JSON.stringify({ user_id: userId, warranty_id: warrantyId })
      }).then(r => r.json())
      setPredictive(pred)
      renderChart(pred)
      setStatus('Loaded')
    } catch (err) {
      console.error(err)
      setStatus('Error')
    }
  }

  const renderChart = (pred) => {
    const ctx = document.getElementById('chart')
    if (!ctx) return
    if (chartRef) {
      chartRef.destroy()
    }
    const c = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Predictive'],
        datasets: [{ label: 'Score', data: [pred?.score || 0], backgroundColor: '#1f7ae0' }]
      },
      options: { scales: { y: { min: 0, max: 1 } } }
    })
    setChartRef(c)
  }

  return (
    <div className="app">
      <header><h1>Smart Warranty Hub Dashboard</h1></header>
      <main>
        <div className="card">
          <label>User ID</label>
          <input value={userId} onChange={e => setUserId(e.target.value)} />
          <label>Warranty ID</label>
          <input value={warrantyId} onChange={e => setWarrantyId(e.target.value)} />
          <button onClick={load}>Load</button>
          <div className="status">{status}</div>
        </div>
        <div className="card"><h3>Warranty</h3><pre>{warranty ? JSON.stringify(warranty, null, 2) : ''}</pre></div>
        <div className="card"><h3>Summary</h3><pre>{summary}</pre></div>
        <div className="card"><h3>Advisories</h3>{nudges.map((n,i)=><div key={i} className="nudge"><strong>{n.title}</strong><div>{n.message}</div></div>)}</div>
        <div className="card"><h3>Scores</h3><canvas id="chart"></canvas></div>
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
