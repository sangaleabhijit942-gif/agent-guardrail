# Developer Onboarding — Agent Guardrail

Welcome. Before Friday, please complete everything below so we can start building immediately.

## 1. What we're building
A SaaS product that installs a monitoring SDK inside a customer's LangGraph AI agent application. It watches agent execution in real time, detects runaway loops and cost spikes (ping-pong between agents, tool-call thrashing, context bloat), and automatically kills or throttles the workflow before it wastes money — alerting the customer immediately. Read `ARCHITECTURE.md`, `CONVENTIONS.md`, and `CLAUDE.md` in the repo root before writing any code — these are not optional reading.

## 2. Tech stack
- Backend (`sdk/`, `ingestion-api/`, `policy-engine/`): **Python**
- Frontend (`dashboard/`): **TypeScript + React**
- Databases: Supabase (Postgres — accounts/config), ClickHouse (event/trace data), Upstash Redis (queue)

## 3. Install before Friday
- **Python 3.11+**: https://www.python.org/downloads/ — during install on Windows, check the box "Add Python to PATH."
- **Node.js 20+** (for the dashboard): https://nodejs.org — download the "LTS" version.
- **Git**: https://git-scm.com/downloads
- **VS Code**: https://code.visualstudio.com
- **Docker Desktop** (for running things locally in a consistent way): https://www.docker.com/products/docker-desktop/

## 4. Get repo access
1. Accept the GitHub org invite sent to sangaleabhijit942@gmail.com.
2. Clone the repo:
git clone https://github.com/sangaleabhijit942-gif/agent-guardrail.git

## 5. Contact & Support
If you have any questions or run into issues:
- *Email:* sangaleabhijit942@gmail.com
- *Phone / WhatsApp:* +91 9930988406