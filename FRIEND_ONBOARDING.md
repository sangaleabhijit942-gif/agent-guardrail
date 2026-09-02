## Step 1 — Get your API key

**⚠️ Windows users: use PowerShell's `Invoke-WebRequest` block below, NOT
the `curl` block — even though PowerShell recognizes the word `curl`, it's
actually a different command underneath and the `curl`-style syntax will
error. Use whichever block matches your actual OS.**

Run this once, from anywhere:
# Agent Guardrail — Quick Start Guide

This guide gets your AI agent protected by Agent Guardrail in about 5 minutes.
No sales call, no config files to hunt for — just a few lines of code.

**Quick note on what's one-time vs. every run:**
Steps 1, 2, and 4 are things you do **once**, ever (or once per new workflow
for Step 4). Step 3 is code you write **once**, into your agent's file — after
that, it just runs automatically every time you run your agent, like any
other part of your code. You never repeat these steps manually before each run.

---

## What this does

Agent Guardrail watches your agent's spending in real time. You set a budget
(dollars or tokens) per workflow, and it stops your agent automatically the
moment it crosses that line — before a bug, a retry loop, or an oversized
input turns into a surprise bill.

---

## Step 1 — Get your API key

Run this once, from anywhere:

**Windows PowerShell:**
```powershell
Invoke-WebRequest -Uri "https://agent-guardrail-api-b3ex.onrender.com/signup" -Method POST -ContentType "application/json" -Body '{"name": "YOUR NAME HERE"}' -UseBasicParsing
```

**Mac/Linux/curl:**
```bash
curl -X POST https://agent-guardrail-api-b3ex.onrender.com/signup \
  -H "Content-Type: application/json" \
  -d '{"name": "YOUR NAME HERE"}'
```

You'll get back something like:
```json
{
  "customer_id": "cust-a1b2c3d4",
  "api_key": "ag_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
  "warning": "Save this API key now — it will not be shown again."
}
```

**Save the `api_key` somewhere safe right now.** It's shown exactly once.

**Note:** the first request after a period of inactivity can take up to
30-60 seconds to respond (our hosting's free tier "wakes up" on first use).
This is normal — just wait, don't assume it's broken.

---

## Step 2 — Install the 
pip install git+https://github.com/sangaleabhijit942-gif/agent-guardrail-sdk.git

---
## Before Step 3 — make sure your own Anthropic API key is set

Agent Guardrail works alongside your existing Anthropic setup — it doesn't
provide LLM access itself. Before adding Agent Guardrail, confirm your own
agent already works and can make real Anthropic calls, with your own API
key set as an environment variable:

**Windows PowerShell:**
```powershell
$env:ANTHROPIC_API_KEY = "your-own-anthropic-key-here"
```

**Mac/Linux:**
```bash
export ANTHROPIC_API_KEY="your-own-anthropic-key-here"
```

If you skip this, you'll see a confusing `WorkloadIdentityError` or
`invalid_grant` error when your agent tries to make its first LLM call —
that error is coming from Anthropic's own library, not from Agent Guardrail,
and it means your Anthropic key isn't set correctly, not that anything is
broken on our end.


## Step 3 — Add it to your agent

At the top of your agent's Python file, wherever you create your Anthropic
(or other LLM) client:

```python
from agentguardrail import GuardrailClient, GuardrailKillSignal

guardrail = GuardrailClient(
    api_key="YOUR_API_KEY_FROM_STEP_1",
    workflow_name="my-agent-workflow",
    base_url="https://agent-guardrail-api-b3ex.onrender.com",
    timeout=15   # extra time for our hosting's occasional cold-start delay
)
```

**In every place your agent makes an LLM call**, report the usage right
after the call:

```python
response = client.messages.create(...)   # your existing LLM call, unchanged

guardrail.track(
    node_name="whatever_step_this_is",    # any label, just for your own logs
    step=0,
    message="short description of what happened",
    tokens_in=response.usage.input_tokens,
    tokens_out=response.usage.output_tokens
)
```

**Wrap your agent's main loop to catch the stop signal:**

```python
try:
    # ... your agent's normal execution ...
except GuardrailKillSignal as e:
    print(f"[STOPPED BY AGENT GUARDRAIL] {e}")
    # your agent stops here — this is correct, expected behavior
```

### If your agent has multiple nodes/roles (e.g. a Generator + Critic loop)

**Add a `guardrail.track()` call after EVERY node that makes a real LLM call**
— not just one. If your Generator makes a call and your Critic makes a
separate call, both need their own `guardrail.track()`. As long as both use
the **same `guardrail` instance** (created once, shared across your whole
graph), Agent Guardrail correctly adds up the total cost across all of them
— it doesn't matter that they're "different" nodes; the combined spend on
this workflow is what gets checked against your threshold.

### Note for multi-turn / self-refining agents

If your agent re-sends growing history each iteration (like a
Generator-Critic refinement loop that keeps accumulating a `draft_history`
across rounds), per-call cost will climb steadily by design — this is
expected, not a bug in Agent Guardrail. **Start with a higher threshold than
you think you need**, watch the dashboard for a few real runs, then tighten
it once you see your actual per-iteration cost pattern. If you notice cost
climbing every round even when your task doesn't seem to need it, that's
often a sign your own history/context isn't being trimmed between rounds —
worth checking your own code, separate from anything Agent Guardrail does.

---

## Step 4 — Set your budget

Before running your agent, tell Agent Guardrail how much this workflow is
allowed to spend:

**Windows PowerShell:**
```powershell
Invoke-WebRequest -Uri "https://agent-guardrail-api-b3ex.onrender.com/thresholds" -Method POST -ContentType "application/json" -Headers @{"X-API-Key"="YOUR_API_KEY_FROM_STEP_1"} -Body '{"workflow_name": "my-agent-workflow", "threshold_type": "cost", "threshold": 1.00}' -UseBasicParsing
```

**Mac/Linux/curl:**
```bash
curl -X POST https://agent-guardrail-api-b3ex.onrender.com/thresholds \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY_FROM_STEP_1" \
  -d '{"workflow_name": "my-agent-workflow", "threshold_type": "cost", "threshold": 1.00}'
```

This example caps `my-agent-workflow` at **$1.00**. You can also use
`"threshold_type": "tokens"` with a `"threshold"` in raw token count instead
of dollars — whichever you prefer.

---

## Step 5 — Run it

That's it. Run your agent normally. If it stays under budget, nothing changes
— you'll never notice Agent Guardrail is there. If it crosses the line, it
stops automatically and prints exactly why.

---

## Optional — stronger protection (recommended once Step 5 works)

The steps above tell your agent to stop *after* it's told to. For real,
guaranteed protection — where the API call is blocked *before* it's even
sent, regardless of your own error handling — add two more lines:

```python
guardrail.start_background_sync()
guardrail.patch_anthropic(client)   # 'client' = your anthropic.Anthropic(...) instance
```

Add these right after you create both `guardrail` and your Anthropic
`client`. With this on, if your budget is exceeded, the LLM call is never
made at all — you'll see a `BudgetExceededError` instead of `GuardrailKillSignal`.

---

## Questions / something not working?

Message me directly — this is a real, working product, but you're one of
the first people using it outside my own testing, so if something's
confusing or broken, that's genuinely useful for me to know.