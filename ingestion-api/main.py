from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, UTC
from dotenv import load_dotenv
from clickhouse_client import get_client

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ch_client = get_client()

INPUT_COST_PER_TOKEN = 1 / 1_000_000
OUTPUT_COST_PER_TOKEN = 5 / 1_000_000
KILL_THRESHOLD = 0.01  # fallback default when no per-workflow threshold is configured

class TraceEvent(BaseModel):
    node_name: str
    step: int
    message: str
    trace_id: str = "default-run"
    workflow_name: str = "default-workflow"
    tokens_in: int = 0
    tokens_out: int = 0

class ThresholdConfig(BaseModel):
    workflow_name: str
    threshold: float

def get_threshold(workflow_name: str) -> float:
    result = ch_client.query(
        "SELECT threshold FROM workflow_thresholds FINAL WHERE workflow_name = {name:String}",
        parameters={"name": workflow_name}
    )
    if result.result_rows:
        return result.result_rows[0][0]
    return KILL_THRESHOLD

@app.post("/thresholds")
async def set_threshold(config: ThresholdConfig):
    ch_client.insert(
        "workflow_thresholds",
        [[config.workflow_name, config.threshold]],
        column_names=["workflow_name", "threshold"]
    )
    return {"status": "ok", "workflow_name": config.workflow_name, "threshold": config.threshold}

@app.post("/events")
async def receive_event(event: TraceEvent):
    event_cost = (event.tokens_in * INPUT_COST_PER_TOKEN) + (event.tokens_out * OUTPUT_COST_PER_TOKEN)

    ch_client.insert(
        "agent_events",
        [[event.trace_id, event.node_name, event.step, event.message, event.tokens_in, event.tokens_out, event_cost, datetime.now(UTC)]],
        column_names=["trace_id", "node_name", "step", "message", "tokens_in", "tokens_out", "cost", "timestamp"]
    )

    result = ch_client.query(
        "SELECT SUM(cost) FROM agent_events WHERE trace_id = {trace_id:String}",
        parameters={"trace_id": event.trace_id}
    )
    current_cost = result.result_rows[0][0] or 0.0

    threshold = get_threshold(event.workflow_name)

    print(f"[RECEIVED] {datetime.now(UTC).isoformat()} | Node: {event.node_name} | Step: {event.step} | {event.message} | Tokens: {event.tokens_in}in/{event.tokens_out}out | Cost so far: ${current_cost:.6f} | Threshold: ${threshold:.6f}")

    if current_cost >= threshold:
        print(f"[KILL SIGNAL] Trace '{event.trace_id}' exceeded ${threshold:.6f} — signaling kill")
        return {"status": "kill", "reason": f"Cost threshold exceeded: ${current_cost:.6f}"}

    return {"status": "ok"}

@app.get("/workflows")
async def list_workflows():
    result = ch_client.query(
        "SELECT trace_id, SUM(cost) as total_cost FROM agent_events GROUP BY trace_id"
    )
    workflows = []
    for row in result.result_rows:
        trace_id, cost = row
        workflows.append({
            "trace_id": trace_id,
            "cost": round(cost, 6),
            "limit": KILL_THRESHOLD,
            "status": "killed" if cost >= KILL_THRESHOLD else "active"
        })
    return {"workflows": workflows}

@app.get("/stats")
async def get_stats():
    result = ch_client.query(
        "SELECT trace_id, SUM(cost) as total_cost FROM agent_events GROUP BY trace_id"
    )
    all_costs = [row[1] for row in result.result_rows]
    killed = [c for c in all_costs if c >= KILL_THRESHOLD]
    total_saved = len(killed) * KILL_THRESHOLD
    return {
        "total_workflows": len(all_costs),
        "killed_count": len(killed),
        "estimated_saved": round(total_saved, 6)
    }