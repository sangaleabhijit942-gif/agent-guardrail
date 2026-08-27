from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, UTC
from dotenv import load_dotenv
from clickhouse_client import get_client
import secrets
import uuid

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
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
    threshold_type: str = "cost"
    threshold: float = 0.0
    token_threshold: int = 0

class SignupRequest(BaseModel):
    name: str

def get_current_customer(x_api_key: str = Header(...)) -> str:
    client = get_client()
    result = client.query(
        "SELECT customer_id FROM customers FINAL WHERE api_key = {key:String}",
        parameters={"key": x_api_key}
    )
    if not result.result_rows:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return result.result_rows[0][0]

def get_threshold_config(customer_id: str, workflow_name: str) -> dict:
    client = get_client()
    result = client.query(
        "SELECT threshold, threshold_type, token_threshold FROM workflow_thresholds FINAL WHERE workflow_name = {name:String} AND customer_id = {cust:String}",
        parameters={"name": workflow_name, "cust": customer_id}
    )
    if result.result_rows:
        threshold, threshold_type, token_threshold = result.result_rows[0]
        return {"threshold": threshold, "threshold_type": threshold_type, "token_threshold": token_threshold}
    return {"threshold": KILL_THRESHOLD, "threshold_type": "cost", "token_threshold": 0}

def classify_retry_pattern(intervals: list) -> dict:
    """
    Classify why repeated calls are happening, based purely on timing intervals
    between events. Uses no customer code or content — only timestamps already stored.
    """
    if len(intervals) < 3:
        return {"pattern": "insufficient_data", "confidence": "none", "description": "Not enough repeated calls to classify reliably."}

    avg = sum(intervals) / len(intervals)

    if all(i < 1.0 for i in intervals):
        return {
            "pattern": "tight_loop",
            "confidence": "high",
            "description": "All calls arriving within a second of each other. Consistent with a loop retrying immediately, often where an error is being caught and ignored."
        }

    is_monotonic_growth = all(
        intervals[i] >= intervals[i - 1] * 1.5
        for i in range(1, len(intervals))
    )
    if is_monotonic_growth:
        return {
            "pattern": "exponential_backoff",
            "confidence": "high",
            "description": "Intervals between calls increase geometrically with each attempt. Consistent with automatic retry logic in an HTTP client or agent framework."
        }

    variance = sum((i - avg) ** 2 for i in intervals) / len(intervals)
    std_dev = variance ** 0.5
    if avg > 10 and std_dev < avg * 0.15:
        return {
            "pattern": "periodic_restart",
            "confidence": "medium",
            "description": f"Calls arriving at a consistent ~{int(avg)}s interval. Consistent with a process being restarted on a schedule, such as by a supervisor or scheduler."
        }

    return {
        "pattern": "irregular",
        "confidence": "low",
        "description": "Repeated calls detected, but the timing does not match a known automated retry signature. This may indicate manual runs, variable workload, or a pattern not yet recognised."
    }

@app.post("/signup")
async def signup(req: SignupRequest):
    client = get_client()
    new_customer_id = f"cust-{uuid.uuid4().hex[:8]}"
    new_api_key = f"ag_{secrets.token_urlsafe(32)}"

    client.insert(
        "customers",
        [[new_customer_id, req.name, new_api_key, datetime.now(UTC)]],
        column_names=["customer_id", "name", "api_key", "created_at"]
    )

    return {
        "customer_id": new_customer_id,
        "api_key": new_api_key,
        "warning": "Save this API key now — it will not be shown again."
    }

@app.post("/thresholds")
async def set_threshold(config: ThresholdConfig, customer_id: str = Depends(get_current_customer)):
    client = get_client()
    client.insert(
        "workflow_thresholds",
        [[config.workflow_name, config.threshold, datetime.now(UTC), customer_id, config.threshold_type, config.token_threshold]],
        column_names=["workflow_name", "threshold", "updated_at", "customer_id", "threshold_type", "token_threshold"]
    )
    return {
        "status": "ok",
        "workflow_name": config.workflow_name,
        "threshold_type": config.threshold_type,
        "threshold": config.threshold,
        "token_threshold": config.token_threshold
    }

@app.post("/events")
async def receive_event(event: TraceEvent, customer_id: str = Depends(get_current_customer)):
    client = get_client()
    event_cost = (event.tokens_in * INPUT_COST_PER_TOKEN) + (event.tokens_out * OUTPUT_COST_PER_TOKEN)

    client.insert(
        "agent_events",
        [[event.trace_id, event.node_name, event.step, event.message, event.tokens_in, event.tokens_out, event_cost, datetime.now(UTC), customer_id, event.workflow_name]],
        column_names=["trace_id", "node_name", "step", "message", "tokens_in", "tokens_out", "cost", "timestamp", "customer_id", "workflow_name"]
    )

    result = client.query(
        "SELECT SUM(cost), SUM(tokens_in) + SUM(tokens_out) FROM agent_events WHERE trace_id = {trace_id:String} AND customer_id = {cust:String}",
        parameters={"trace_id": event.trace_id, "cust": customer_id}
    )
    current_cost, current_tokens = result.result_rows[0]
    current_cost = current_cost or 0.0
    current_tokens = current_tokens or 0

    config = get_threshold_config(customer_id, event.workflow_name)

    if config["threshold_type"] == "tokens":
        limit_reached = current_tokens >= config["token_threshold"]
        print(f"[RECEIVED] {datetime.now(UTC).isoformat()} | Customer: {customer_id} | Node: {event.node_name} | Step: {event.step} | {event.message} | Tokens: {event.tokens_in}in/{event.tokens_out}out | Total tokens: {current_tokens} | Token limit: {config['token_threshold']}")
        if limit_reached:
            print(f"[KILL SIGNAL] Trace '{event.trace_id}' exceeded {config['token_threshold']} tokens — signaling kill")
            return {"status": "kill", "reason": f"Token threshold exceeded: {current_tokens} tokens"}
    else:
        limit_reached = current_cost >= config["threshold"]
        print(f"[RECEIVED] {datetime.now(UTC).isoformat()} | Customer: {customer_id} | Node: {event.node_name} | Step: {event.step} | {event.message} | Tokens: {event.tokens_in}in/{event.tokens_out}out | Cost so far: ${current_cost:.6f} | Threshold: ${config['threshold']:.6f}")
        if limit_reached:
            print(f"[KILL SIGNAL] Trace '{event.trace_id}' exceeded ${config['threshold']:.6f} — signaling kill")
            return {"status": "kill", "reason": f"Cost threshold exceeded: ${current_cost:.6f}"}

    return {"status": "ok"}

@app.get("/workflows")
async def list_workflows(customer_id: str = Depends(get_current_customer)):
    client = get_client()
    result = client.query(
        """
        SELECT
            trace_id,
            any(workflow_name) as workflow_name,
            SUM(cost) as total_cost,
            SUM(tokens_in) + SUM(tokens_out) as total_tokens
        FROM agent_events
        WHERE customer_id = {cust:String}
        GROUP BY trace_id
        """,
        parameters={"cust": customer_id}
    )

    workflows = []
    for row in result.result_rows:
        trace_id, workflow_name, cost, tokens = row
        cost = cost or 0.0
        tokens = tokens or 0
        config = get_threshold_config(customer_id, workflow_name)

        if config["threshold_type"] == "tokens":
            limit_value = config["token_threshold"]
            current_value = tokens
            status = "killed" if tokens >= config["token_threshold"] else "active"
            display_type = "tokens"
        else:
            limit_value = config["threshold"]
            current_value = cost
            status = "killed" if cost >= config["threshold"] else "active"
            display_type = "cost"

        workflows.append({
            "trace_id": trace_id,
            "workflow_name": workflow_name,
            "threshold_type": display_type,
            "cost": round(cost, 6),
            "tokens": tokens,
            "current_value": current_value,
            "limit": limit_value,
            "status": status
        })
    return {"workflows": workflows}

@app.get("/stats")
async def get_stats(customer_id: str = Depends(get_current_customer)):
    client = get_client()
    result = client.query(
        """
        SELECT
            trace_id,
            any(workflow_name) as workflow_name,
            SUM(cost) as total_cost,
            SUM(tokens_in) + SUM(tokens_out) as total_tokens
        FROM agent_events
        WHERE customer_id = {cust:String}
        GROUP BY trace_id
        """,
        parameters={"cust": customer_id}
    )

    killed_count = 0
    estimated_saved = 0.0
    for row in result.result_rows:
        trace_id, workflow_name, cost, tokens = row
        cost = cost or 0.0
        tokens = tokens or 0
        config = get_threshold_config(customer_id, workflow_name)

        if config["threshold_type"] == "tokens":
            if tokens >= config["token_threshold"]:
                killed_count += 1
                estimated_saved += config["token_threshold"] * ((INPUT_COST_PER_TOKEN + OUTPUT_COST_PER_TOKEN) / 2)
        else:
            if cost >= config["threshold"]:
                killed_count += 1
                estimated_saved += config["threshold"]

    return {
        "total_workflows": len(result.result_rows),
        "killed_count": killed_count,
        "estimated_saved": round(estimated_saved, 6)
    }

@app.get("/diagnostics/{trace_id}")
async def get_trace_diagnostics(trace_id: str, customer_id: str = Depends(get_current_customer)):
    client = get_client()

    result = client.query(
        """
        SELECT timestamp, node_name, message
        FROM agent_events
        WHERE trace_id = {trace_id:String} AND customer_id = {cust:String}
        ORDER BY timestamp ASC
        """,
        parameters={"trace_id": trace_id, "cust": customer_id}
    )

    rows = result.result_rows
    if len(rows) < 2:
        return {
            "trace_id": trace_id,
            "event_count": len(rows),
            "analysis": {"pattern": "insufficient_data", "confidence": "none", "description": "Not enough events to analyze."}
        }

    timestamps = [row[0] for row in rows]
    intervals = [
        (timestamps[i] - timestamps[i - 1]).total_seconds()
        for i in range(1, len(timestamps))
    ]

    analysis = classify_retry_pattern(intervals)

    return {
        "trace_id": trace_id,
        "event_count": len(rows),
        "first_event": timestamps[0].isoformat(),
        "last_event": timestamps[-1].isoformat(),
        "duration_seconds": round((timestamps[-1] - timestamps[0]).total_seconds(), 2),
        "intervals_seconds": [round(i, 3) for i in intervals],
        "analysis": analysis
    }