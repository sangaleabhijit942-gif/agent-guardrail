from fastapi import FastAPI, Header, HTTPException, Depends
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

INPUT_COST_PER_TOKEN = 1 / 1_000_000
OUTPUT_COST_PER_TOKEN = 5 / 1_000_000
KILL_THRESHOLD = 0.01

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

def get_current_customer(x_api_key: str = Header(...)) -> str:
    client = get_client()
    result = client.query(
        "SELECT customer_id FROM customers FINAL WHERE api_key = {key:String}",
        parameters={"key": x_api_key}
    )
    if not result.result_rows:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return result.result_rows[0][0]

def get_threshold(customer_id: str, workflow_name: str) -> float:
    client = get_client()
    result = client.query(
        "SELECT threshold FROM workflow_thresholds FINAL WHERE workflow_name = {name:String} AND customer_id = {cust:String}",
        parameters={"name": workflow_name, "cust": customer_id}
    )
    if result.result_rows:
        return result.result_rows[0][0]
    return KILL_THRESHOLD

@app.post("/thresholds")
async def set_threshold(config: ThresholdConfig, customer_id: str = Depends(get_current_customer)):
    client = get_client()
    client.insert(
        "workflow_thresholds",
        [[config.workflow_name, config.threshold, datetime.now(UTC), customer_id]],
        column_names=["workflow_name", "threshold", "updated_at", "customer_id"]
    )
    return {"status": "ok", "workflow_name": config.workflow_name, "threshold": config.threshold}

@app.post("/events")
async def receive_event(event: TraceEvent, customer_id: str = Depends(get_current_customer)):
    client = get_client()
    event_cost = (event.tokens_in * INPUT_COST_PER_TOKEN) + (event.tokens_out * OUTPUT_COST_PER_TOKEN)

    client.insert(
        "agent_events",
        [[event.trace_id, event.node_name, event.step, event.message, event.tokens_in, event.tokens_out, event_cost, datetime.now(UTC), customer_id]],
        column_names=["trace_id", "node_name", "step", "message", "tokens_in", "tokens_out", "cost", "timestamp", "customer_id"]
    )

    result = client.query(
        "SELECT SUM(cost) FROM agent_events WHERE trace_id = {trace_id:String} AND customer_id = {cust:String}",
        parameters={"trace_id": event.trace_id, "cust": customer_id}
    )
    current_cost = result.result_rows[0][0] or 0.0

    threshold = get_threshold(customer_id, event.workflow_name)

    print(f"[RECEIVED] {datetime.now(UTC).isoformat()} | Customer: {customer_id} | Node: {event.node_name} | Step: {event.step} | {event.message} | Tokens: {event.tokens_in}in/{event.tokens_out}out | Cost so far: ${current_cost:.6f} | Threshold: ${threshold:.6f}")

    if current_cost >= threshold:
        print(f"[KILL SIGNAL] Trace '{event.trace_id}' exceeded ${threshold:.6f} — signaling kill")
        return {"status": "kill", "reason": f"Cost threshold exceeded: ${current_cost:.6f}"}

    return {"status": "ok"}

@app.get("/workflows")
async def list_workflows(customer_id: str = Depends(get_current_customer)):
    client = get_client()
    result = client.query(
        "SELECT trace_id, SUM(cost) as total_cost FROM agent_events WHERE customer_id = {cust:String} GROUP BY trace_id",
        parameters={"cust": customer_id}
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
async def get_stats(customer_id: str = Depends(get_current_customer)):
    client = get_client()
    result = client.query(
        "SELECT trace_id, SUM(cost) as total_cost FROM agent_events WHERE customer_id = {cust:String} GROUP BY trace_id",
        parameters={"cust": customer_id}
    )
    all_costs = [row[1] for row in result.result_rows]
    killed = [c for c in all_costs if c >= KILL_THRESHOLD]
    total_saved = len(killed) * KILL_THRESHOLD
    return {
        "total_workflows": len(all_costs),
        "killed_count": len(killed),
        "estimated_saved": round(total_saved, 6)
    }