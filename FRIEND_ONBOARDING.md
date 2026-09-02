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

## Step 2 — Install the SDK