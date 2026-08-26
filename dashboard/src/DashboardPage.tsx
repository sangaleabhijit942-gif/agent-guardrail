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

const API_KEY = "ag_test_51f8a3c2e94b4d7a9c1f6e8b2a3d5c7f"

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

function buildInsight(stats: Stats): string {
  if (stats.total_workflows === 0) {
    return 'No workflows monitored yet. Run an agent to see live activity here.'
  }
  if (stats.killed_count === 0) {
    return `All ${stats.total_workflows} monitored workflow${stats.total_workflows > 1 ? 's are' : ' is'} running within budget. No interventions needed.`
  }
  return `${stats.killed_count} workflow${stats.killed_count > 1 ? 's have' : ' has'} been stopped for exceeding cost limits — an estimated $${stats.estimated_saved.toFixed(6)} saved so far.`
}

function ThresholdForm({ onSaved }: { onSaved: () => void }) {
  const [workflowName, setWorkflowName] = useState('')
  const [thresholdType, setThresholdType] = useState<'cost' | 'tokens'>('cost')
  const [value, setValue] = useState('')
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  const handleSave = () => {
    if (!workflowName.trim() || !value.trim()) return
    setStatus('saving')

    const body =
      thresholdType === 'cost'
        ? {
            workflow_name: workflowName.trim(),
            threshold_type: 'cost',
            threshold: parseFloat(value),
            token_threshold: 0
          }
        : {
            workflow_name: workflowName.trim(),
            threshold_type: 'tokens',
            threshold: 0,
            token_threshold: parseInt(value, 10)
          }

    fetch('http://localhost:8000/thresholds', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY
      },
      body: JSON.stringify(body)
    })
      .then((res) => {
        if (!res.ok) throw new Error('Request failed')
        return res.json()
      })
      .then(() => {
        setStatus('saved')
        setWorkflowName('')
        setValue('')
        onSaved()
        setTimeout(() => setStatus('idle'), 2000)
      })
      .catch(() => setStatus('error'))
  }

  return (
    <div className="threshold-form">
      <div className="section-title">Set a workflow threshold</div>
      <div className="threshold-type-toggle">
        <button
          className={`threshold-type-btn ${thresholdType === 'cost' ? 'threshold-type-active' : ''}`}
          onClick={() => setThresholdType('cost')}
        >
          Cost ($)
        </button>
        <button
          className={`threshold-type-btn ${thresholdType === 'tokens' ? 'threshold-type-active' : ''}`}
          onClick={() => setThresholdType('tokens')}
        >
          Tokens
        </button>
      </div>
      <div className="threshold-form-row">
        <input
          type="text"
          placeholder="workflow name (e.g. support-bot)"
          value={workflowName}
          onChange={(e) => setWorkflowName(e.target.value)}
          className="threshold-input"
        />
        <input
          type="number"
          step={thresholdType === 'cost' ? '0.0001' : '1'}
          placeholder={thresholdType === 'cost' ? 'threshold ($)' : 'threshold (tokens)'}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="threshold-input threshold-input-narrow"
        />
        <button onClick={handleSave} disabled={status === 'saving'} className="threshold-button">
          {status === 'saving' ? 'Saving...' : 'Save'}
        </button>
      </div>
      {status === 'saved' && <div className="threshold-message threshold-success">Threshold saved.</div>}
      {status === 'error' && <div className="threshold-message threshold-error">Failed to save. Check the API is running.</div>}
    </div>
  )
}

interface SignupResult {
  customer_id: string
  api_key: string
  warning: string
}

function SignupPanel({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('')
  const [status, setStatus] = useState<'idle' | 'saving' | 'error'>('idle')
  const [result, setResult] = useState<SignupResult | null>(null)
  const [copied, setCopied] = useState(false)

  const handleSignup = () => {
    if (!name.trim()) return
    setStatus('saving')

    fetch('http://localhost:8000/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim() })
    })
      .then((res) => {
        if (!res.ok) throw new Error('Signup failed')
        return res.json()
      })
      .then((data: SignupResult) => {
        setResult(data)
        setStatus('idle')
      })
      .catch(() => setStatus('error'))
  }

  const handleCopy = () => {
    if (!result) return
    navigator.clipboard.writeText(result.api_key)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (result) {
    return (
      <div className="signup-panel">
        <div className="signup-result-warning">{result.warning}</div>
        <div className="signup-field">
          <div className="signup-field-label">Customer ID</div>
          <div className="signup-field-value">{result.customer_id}</div>
        </div>
        <div className="signup-field">
          <div className="signup-field-label">API Key</div>
          <div className="signup-field-value signup-key">{result.api_key}</div>
        </div>
        <div className="signup-actions">
          <button onClick={handleCopy} className="threshold-button">
            {copied ? 'Copied!' : 'Copy API Key'}
          </button>
          <button onClick={onClose} className="signup-close-button">Done</button>
        </div>
      </div>
    )
  }

  return (
    <div className="signup-panel">
      <div className="signup-field-label">Your name</div>
      <input
        type="text"
        placeholder="Jane Doe"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="threshold-input"
      />
      <div className="signup-actions">
        <button onClick={handleSignup} disabled={status === 'saving'} className="threshold-button">
          {status === 'saving' ? 'Creating account...' : 'Create account'}
        </button>
        <button onClick={onClose} className="signup-close-button">Cancel</button>
      </div>
      {status === 'error' && <div className="threshold-message threshold-error">Signup failed. Check the API is running.</div>}
    </div>
  )
}

function DashboardPage() {
  const [workflows, setWorkflows] = useState<WorkflowGauge[]>([])
  const [stats, setStats] = useState<Stats>({ total_workflows: 0, killed_count: 0, estimated_saved: 0 })
  const [showSignup, setShowSignup] = useState(false)

  const fetchData = () => {
    fetch('http://localhost:8000/workflows', {
      headers: { 'X-API-Key': API_KEY }
    })
      .then((res) => res.json())
      .then((data) => setWorkflows(data.workflows))
      .catch((err) => console.error('Failed to fetch workflows:', err))

    fetch('http://localhost:8000/stats', {
      headers: { 'X-API-Key': API_KEY }
    })
      .then((res) => res.json())
      .then((data) => setStats(data))
      .catch((err) => console.error('Failed to fetch stats:', err))
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 3000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div className="greeting">
          Good afternoon, <span>Abhijit</span>
        </div>
        {!showSignup && (
          <button onClick={() => setShowSignup(true)} className="signup-open-button">
            + New account
          </button>
        )}
      </div>

      {showSignup && <SignupPanel onClose={() => setShowSignup(false)} />}

      <div className={`insight-card ${stats.killed_count > 0 ? 'insight-warn' : 'insight-safe'}`}>
        <span className="insight-dot" />
        <span className="insight-text">{buildInsight(stats)}</span>
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

      <ThresholdForm onSaved={fetchData} />

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

export default DashboardPage