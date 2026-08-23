type GaugeStatus = 'safe' | 'warn' | 'danger'

interface WorkflowGauge {
  name: string
  currentCost: number
  limit: number
}

function getStatus(pct: number): GaugeStatus {
  if (pct >= 100) return 'danger'
  if (pct >= 70) return 'warn'
  return 'safe'
}

function Gauge({ workflow }: { workflow: WorkflowGauge }) {
  const pct = Math.min((workflow.currentCost / workflow.limit) * 100, 100)
  const status = getStatus(pct)
  const color = status === 'danger' ? 'var(--danger)' : status === 'warn' ? 'var(--warn)' : 'var(--safe)'

  return (
    <div className="gauge-row">
      <div className="gauge-header">
        <span className="gauge-name">{workflow.name}</span>
        <span className="gauge-cost">
          ${workflow.currentCost.toFixed(2)} / ${workflow.limit.toFixed(2)}
        </span>
      </div>
      <div className="gauge-track">
        <div className="gauge-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  )
}

function App() {
  const placeholderWorkflows: WorkflowGauge[] = [
    { name: 'support-bot-run-4482', currentCost: 0.12, limit: 0.20 },
    { name: 'research-agent-run-91', currentCost: 0.20, limit: 0.20 },
    { name: 'code-review-agent-run-17', currentCost: 0.05, limit: 0.50 },
  ]

  return (
    <div className="dashboard">
      <div className="greeting">
        Good afternoon, <span>Abhijit</span>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Workflows monitored</div>
          <div className="stat-value">3</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Kills triggered</div>
          <div className="stat-value warn">1</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Estimated saved</div>
          <div className="stat-value safe">$0.00</div>
        </div>
      </div>

      <div className="section-title">Active workflows</div>
      {placeholderWorkflows.map((w) => (
        <Gauge key={w.name} workflow={w} />
      ))}
    </div>
  )
}

export default App