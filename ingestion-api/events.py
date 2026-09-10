"""
KILL PATH — this module contains the decision that terminates a customer's live
workflow. Any change here requires human line-by-line review before merge
(see ARCHITECTURE.md "Hard rule").
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime, UTC
from clickhouse_client import get_client
from auth import get_current_customer
from thresholds import get_threshold_config
from config import INPUT_COST_PER_TOKEN, OUTPUT_COST_PER_TOKEN
from diagnostics import classify_retry_pattern, classify_token_growth
from alerts import check_graduated_alert

router = APIRouter()


class TraceEvent(BaseModel):
    node_name: str
    step: int
    message: str
    trace_id: str = "default-run"
    workflow_name: str = "default-workflow"
    tokens_in: int = 0
    tokens_out: int = 0


def _get_kill_diagnosis(trace_id: str, customer_id: str, client) -> dict:
    """
    Called only at the moment a kill fires, so the customer gets 'why' along
    with 'that it stopped', in the same response — no separate API call needed.
    Reuses the same classification logic as GET /diagnostics/{trace_id}.

    Deliberately wrapped in try/except: diagnosis is an enhancement on top of
    the kill decision, never a dependency of it. If this fails for any reason,
    the kill itself must still succeed and return normally — a broken
    diagnosis must never block or alter the actual stop decision.
    """
    try:
        result = client.query(
            """
            SELECT timestamp, node_name, message, tokens_in
            FROM agent_events
            WHERE trace_id = {trace_id:String} AND customer_id = {cust:String}
            ORDER BY timestamp ASC
            """,
            parameters={"trace_id": trace_id, "cust": customer_id}
        )
        rows = result.result_rows
        if len(rows) < 2:
            return {"pattern": "insufficient_data", "confidence": "none", "description": "Not enough events to analyze."}

        timestamps = [row[0] for row in rows]
        intervals = [
            (timestamps[i] - timestamps[i - 1]).total_seconds()
            for i in range(1, len(timestamps))
        ]
        events_with_tokens = [(row[1], row[3]) for row in rows]

        analysis = classify_token_growth(events_with_tokens)
        if analysis is None:
            analysis = classify_retry_pattern(intervals)
        return analysis
    except Exception as e:
        return {"pattern": "unavailable", "confidence": "none", "description": f"Diagnosis unavailable: {e}"}


@router.post("/events")
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
            diagnosis = _get_kill_diagnosis(event.trace_id, customer_id, client)
            return {
                "status": "kill",
                "reason": f"Token threshold exceeded: {current_tokens} tokens",
                "diagnosis": diagnosis
            }
    else:
        limit_reached = current_cost >= config["threshold"]
        print(f"[RECEIVED] {datetime.now(UTC).isoformat()} | Customer: {customer_id} | Node: {event.node_name} | Step: {event.step} | {event.message} | Tokens: {event.tokens_in}in/{event.tokens_out}out | Cost so far: ${current_cost:.6f} | Threshold: ${config['threshold']:.6f}")
        if limit_reached:
            print(f"[KILL SIGNAL] Trace '{event.trace_id}' exceeded ${config['threshold']:.6f} — signaling kill")
            diagnosis = _get_kill_diagnosis(event.trace_id, customer_id, client)
            return {
                "status": "kill",
                "reason": f"Cost threshold exceeded: ${current_cost:.6f}",
                "diagnosis": diagnosis
            }

    if config["threshold_type"] == "tokens":
        alert = check_graduated_alert(client, event.trace_id, customer_id, current_tokens, config["token_threshold"])
    else:
        alert = check_graduated_alert(client, event.trace_id, customer_id, current_cost, config["threshold"])

    return {"status": "ok", "alert": alert}
    