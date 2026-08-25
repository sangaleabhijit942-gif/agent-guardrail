import { useNavigate } from 'react-router-dom'

function LandingPage() {
  const navigate = useNavigate()

  return (
    <div className="landing">
      <div className="landing-hero">
        <div className="landing-badge">Real-time AI agent cost protection</div>
        <h1 className="landing-title">
          Stop your AI agents before they overspend.
        </h1>
        <p className="landing-subtitle">
          Agent Guardrail watches every call your LangGraph agents make and halts
          them automatically the moment they cross a budget you set — before a
          runaway loop turns into a surprise bill.
        </p>
        <button className="landing-cta" onClick={() => navigate('/dashboard')}>
          Get started
        </button>
      </div>

      <div className="landing-proof">
        <div className="landing-proof-label">Proven in production</div>
        <div className="landing-proof-card">
          <div className="landing-proof-quote">
            "Agent Guardrail caught a real email-processing agent mid-run when a
            single large newsletter pushed it over budget — and stopped it cleanly,
            with zero manual intervention."
          </div>
          <div className="landing-proof-detail">
            Real Gmail agent · Real Claude API calls · Halted at $0.019 before continuing
          </div>
        </div>
      </div>

      <div className="landing-features">
        <div className="landing-feature">
          <div className="landing-feature-title">Set your own budget</div>
          <div className="landing-feature-text">
            Configure a cost threshold per workflow. Agent Guardrail enforces it
            automatically — no code changes needed after setup.
          </div>
        </div>
        <div className="landing-feature">
          <div className="landing-feature-title">Real-time visibility</div>
          <div className="landing-feature-text">
            See exactly which workflows are running, how close they are to their
            limit, and what's already been saved — live.
          </div>
        </div>
        <div className="landing-feature">
          <div className="landing-feature-title">Drop-in SDK</div>
          <div className="landing-feature-text">
            One Python package, a few lines of code. Works alongside your existing
            agent framework without a rewrite.
          </div>
        </div>
      </div>

      <div className="landing-footer">
        <button className="landing-cta-secondary" onClick={() => navigate('/dashboard')}>
          Create your account
        </button>
      </div>
    </div>
  )
}

export default LandingPage