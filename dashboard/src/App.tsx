import { useEffect, useState } from 'react'

type GaugeStatus = 'safe' | 'warn' | 'danger'

interface WorkflowGauge {
  trace_id: string
  cost: number
  limit: number
  status: string
}

interface Stats {
  total_workflows: number
  killed_count: number
  estimated_saved: number
}

function getStatus(pct: number): GaugeStatus {
  if (pct >= 100) return 'danger'
  if (pct >= 70) return 'warn'
  return 'safe'
}

function Gauge({ workflow }: { workflow: WorkflowGauge }) {
  const pct = Math.min((workflow.cost / workflow.limit) * 100, 100)
  const status = getStatus(pct)
  const color = status === 'danger' ? 'var(--danger)' : status === 'warn' ? 'var(--warn)' : 'var(--safe)'

  return (
    <div className="gauge-row">
      <div className="gauge-header">
        <span className="gauge-name">{workflow.trace_id}</span>
        <span className="gauge-cost">
          ${workflow.cost.toFixed(6)} / ${workflow.limit.toFixed(6)}
        </span>
      </div>
      <div className="gauge-track">
        <div className="gauge-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  )
}

function App() {
  const [workflows, setWorkflows] = useState<WorkflowGauge[]>([])
  const [stats, setStats] = useState<Stats>({ total_workflows: 0, killed_count: 0, estimated_saved: 0 })

  useEffect(() => {
    const fetchData = () => {
      fetch('http://localhost:8000/workflows')
        .then((res) => res.json())
        .then((data) => setWorkflows(data.workflows))
        .catch((err) => console.error('Failed to fetch workflows:', err))

      fetch('http://localhost:8000/stats')
        .then((res) => res.json())
        .then((data) => setStats(data))
        .catch((err) => console.error('Failed to fetch stats:', err))
    }
    fetchData()
    const interval = setInterval(fetchData, 3000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="dashboard">
      <div className="greeting">
        Good afternoon, <span>Abhijit</span>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Workflows monitored</div>
          <div className="stat-value">{stats.total_workflows}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Kills triggered</div>
          <div className="stat-value warn">{stats.killed_count}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Estimated saved</div>
          <div className="stat-value safe">${stats.estimated_saved.toFixed(6)}</div>
        </div>
      </div>

      <div className="section-title">Active workflows</div>
      {workflows.length === 0 ? (
        <div className="gauge-row">
          <span className="gauge-cost">No workflows yet. Run a test agent to see data here.</span>
        </div>
      ) : (
        workflows.map((w) => <Gauge key={w.trace_id} workflow={w} />)
      )}
    </div>
  )
}

export default App