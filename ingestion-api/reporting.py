from fastapi import APIRouter, Depends
from clickhouse_client import get_client
from auth import get_current_customer
from thresholds import get_threshold_config
from config import INPUT_COST_PER_TOKEN, OUTPUT_COST_PER_TOKEN

router = APIRouter()


@router.get("/workflows")
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


@router.get("/stats")
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
