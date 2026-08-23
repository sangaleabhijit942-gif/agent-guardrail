import { useEffect, useState } from 'react'

type GaugeStatus = 'safe' | 'warn' | 'danger'

interface WorkflowGauge {
  trace_id: string
  cost: number
  limit: number
  status: string
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
          ${workflow.cost.toFixed(2)} / ${workflow.limit.toFixed(2)}
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

  useEffect(() => {
    const fetchWorkflows = () => {
      fetch('http://localhost:8000/workflows')
        .then((res) => res.json())
        .then((data) => setWorkflows(data.workflows))
        .catch((err) => console.error('Failed to fetch workflows:', err))
    }

    fetchWorkflows()
    const interval = setInterval(fetchWorkflows, 3000)
    return () => clearInterval(interval)
  }, [])

  const killedCount = workflows.filter((w) => w.status === 'killed').length

  return (
    <div className="dashboard">
      <div className="greeting">
        Good afternoon, <span>Abhijit</span>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Workflows monitored</div>
          <div className="stat-value">{workflows.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Kills triggered</div>
          <div className="stat-value warn">{killedCount}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Estimated saved</div>
          <div className="stat-value safe">$0.00</div>
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