from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from datetime import datetime, UTC
from clickhouse_client import get_client
from auth_cache import get_cached_customer_id, set_cached_customer_id
from key_hashing import hash_api_key
import secrets
import uuid

router = APIRouter()


class SignupRequest(BaseModel):
    name: str


def get_current_customer(x_api_key: str = Header(...)) -> str:
    cached_customer_id = get_cached_customer_id(x_api_key)
    if cached_customer_id is not None:
        return cached_customer_id

    incoming_hash = hash_api_key(x_api_key)
    client = get_client()
    result = client.query(
        "SELECT customer_id FROM customers FINAL WHERE api_key_hash = {hash:String}",
        parameters={"hash": incoming_hash}
    )
    if not result.result_rows:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    customer_id = result.result_rows[0][0]
    set_cached_customer_id(x_api_key, customer_id)
    return customer_id


@router.post("/signup")
async def signup(req: SignupRequest):
    client = get_client()
    new_customer_id = f"cust-{uuid.uuid4().hex[:8]}"
    new_api_key = f"ag_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(new_api_key)

    client.insert(
        "customers",
        [[new_customer_id, req.name, key_hash, datetime.now(UTC)]],
        column_names=["customer_id", "name", "api_key_hash", "created_at"]
    )

    return {
        "customer_id": new_customer_id,
        "api_key": new_api_key,
        "warning": "Save this API key now — it will not be shown again."
    }