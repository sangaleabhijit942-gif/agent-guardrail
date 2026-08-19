from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

# Simple in-memory cost tracker: {trace_id: total_cost}
# NOTE: in-memory only, resets if the server restarts — fine for today's prototype
workflow_costs: dict[str, float] = {}

COST_PER_EVENT = 0.05  # fake placeholder cost per node action, replace with real token-based calc later
KILL_THRESHOLD = 0.20  # kill after $0.20 accumulated, for easy testing

class TraceEvent(BaseModel):
    node_name: str
    step: int
    message: str
    trace_id: str = "default-run"  # temporary placeholder until real trace IDs are added

@app.post("/events")
async def receive_event(event: TraceEvent):
    workflow_costs[event.trace_id] = workflow_costs.get(event.trace_id, 0) + COST_PER_EVENT
    current_cost = workflow_costs[event.trace_id]

    print(f"[RECEIVED] {datetime.utcnow().isoformat()} | Node: {event.node_name} | Step: {event.step} | {event.message} | Cost so far: ${current_cost:.2f}")

    if current_cost >= KILL_THRESHOLD:
        print(f"[KILL SIGNAL] Trace '{event.trace_id}' exceeded ${KILL_THRESHOLD:.2f} — signaling kill")
        return {"status": "kill", "reason": f"Cost threshold exceeded: ${current_cost:.2f}"}

    return {"status": "ok"}