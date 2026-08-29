from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from datetime import datetime, UTC
from clickhouse_client import get_client
import secrets
import uuid

router = APIRouter()


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


@router.post("/signup")
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
