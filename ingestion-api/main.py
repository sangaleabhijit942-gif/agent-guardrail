from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

workflow_costs: dict[str, float] = {}
COST_PER_EVENT = 0.05
KILL_THRESHOLD = 0.20

class TraceEvent(BaseModel):
    node_name: str
    step: int
    message: str
    trace_id: str = "default-run"

@app.post("/events")
async def receive_event(event: TraceEvent):
    workflow_costs[event.trace_id] = workflow_costs.get(event.trace_id, 0) + COST_PER_EVENT
    current_cost = workflow_costs[event.trace_id]

    print(f"[RECEIVED] {datetime.utcnow().isoformat()} | Node: {event.node_name} | Step: {event.step} | {event.message} | Cost so far: ${current_cost:.2f}")

    if current_cost >= KILL_THRESHOLD:
        print(f"[KILL SIGNAL] Trace '{event.trace_id}' exceeded ${KILL_THRESHOLD:.2f} — signaling kill")
        return {"status": "kill", "reason": f"Cost threshold exceeded: ${current_cost:.2f}"}

    return {"status": "ok"}

@app.get("/workflows")
async def list_workflows():
    result = []
    for trace_id, cost in workflow_costs.items():
        result.append({
            "trace_id": trace_id,
            "cost": round(cost, 2),
            "limit": KILL_THRESHOLD,
            "status": "killed" if cost >= KILL_THRESHOLD else "active"
        })
    return {"workflows": result}