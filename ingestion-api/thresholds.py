from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime, UTC
from clickhouse_client import get_client
from auth import get_current_customer
from config import KILL_THRESHOLD

router = APIRouter()


class ThresholdConfig(BaseModel):
    workflow_name: str
    threshold_type: str = "cost"
    threshold: float = 0.0
    token_threshold: int = 0


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


@router.get("/threshold-lookup")
async def threshold_lookup(workflow_name: str, customer_id: str = Depends(get_current_customer)):
    """
    Lightweight endpoint for SDK background sync — returns just the threshold
    config for one workflow, in the shape the SDK's local cache expects.
    """
    config = get_threshold_config(customer_id, workflow_name)
    if config["threshold_type"] == "tokens":
        return {"threshold_type": "tokens", "threshold": config["token_threshold"]}
    return {"threshold_type": "cost", "threshold": config["threshold"]}


@router.post("/thresholds")
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
