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

INPUT_COST_PER_TOKEN = 1 / 1_000_000
OUTPUT_COST_PER_TOKEN = 5 / 1_000_000

KILL_THRESHOLD = 0.0001

class TraceEvent(BaseModel):
    node_name: str
    step: int
    message: str
    trace_id: str = "default-run"
    tokens_in: int = 0
    tokens_out: int = 0

@app.post("/events")
async def receive_event(event: TraceEvent):
    event_cost = (event.tokens_in * INPUT_COST_PER_TOKEN) + (event.tokens_out * OUTPUT_COST_PER_TOKEN)
    workflow_costs[event.trace_id] = workflow_costs.get(event.trace_id, 0) + event_cost
    current_cost = workflow_costs[event.trace_id]

    print(f"[RECEIVED] {datetime.utcnow().isoformat()} | Node: {event.node_name} | Step: {event.step} | {event.message} | Tokens: {event.tokens_in}in/{event.tokens_out}out | Cost so far: ${current_cost:.6f}")

    if current_cost >= KILL_THRESHOLD:
        print(f"[KILL SIGNAL] Trace '{event.trace_id}' exceeded ${KILL_THRESHOLD:.2f} — signaling kill")
        return {"status": "kill", "reason": f"Cost threshold exceeded: ${current_cost:.6f}"}

    return {"status": "ok"}

@app.get("/workflows")
async def list_workflows():
    result = []
    for trace_id, cost in workflow_costs.items():
        result.append({
            "trace_id": trace_id,
            "cost": round(cost, 6),
            "limit": KILL_THRESHOLD,
            "status": "killed" if cost >= KILL_THRESHOLD else "active"
        })
    return {"workflows": result}

@app.get("/stats")
async def get_stats():
    killed = [c for c in workflow_costs.values() if c >= KILL_THRESHOLD]
    total_saved = len(killed) * KILL_THRESHOLD
    return {
        "total_workflows": len(workflow_costs),
        "killed_count": len(killed),
        "estimated_saved": round(total_saved, 6)
    }