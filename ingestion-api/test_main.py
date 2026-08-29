from fastapi.testclient import TestClient
from main import app, KILL_THRESHOLD, INPUT_COST_PER_TOKEN, OUTPUT_COST_PER_TOKEN
from auth import get_current_customer
from clickhouse_client import get_client
import pytest
import uuid

# A throwaway customer_id per run. Every row these tests write is tagged with it,
# so cleanup can be scoped to this run and can never touch another tenant's data
# in the shared agent_events table.
TEST_CUSTOMER_ID = f"cust-test-{uuid.uuid4().hex[:8]}"

client = TestClient(app)


def _test_customer() -> str:
    return TEST_CUSTOMER_ID


# These tests exercise the kill/threshold decision, not authentication. Overriding
# the dependency keeps a real API key out of this committed file (CONVENTIONS.md:
# no keys in committed files) and avoids inserting a row into `customers` just to
# run tests. FastAPI keys overrides on the function object, so this applies to
# every route that depends on it, regardless of which module imported it.
app.dependency_overrides[get_current_customer] = _test_customer


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_events():
    yield
    # Scoped DELETE, never TRUNCATE: there is only one ClickHouse database, so a
    # TRUNCATE here would wipe every customer's real event history.
    get_client().command(
        "ALTER TABLE agent_events DELETE WHERE customer_id = {cust:String}",
        parameters={"cust": TEST_CUSTOMER_ID}
    )


@pytest.fixture
def without_auth_override():
    """Restores the real API-key dependency for tests that assert on auth itself."""
    app.dependency_overrides.pop(get_current_customer, None)
    yield
    app.dependency_overrides[get_current_customer] = _test_customer


def send_event(trace_id: str, node_name: str = "TestNode", step: int = 0, tokens_in: int = 0, tokens_out: int = 0):
    return client.post("/events", json={
        "node_name": node_name,
        "step": step,
        "message": "test event",
        "trace_id": trace_id,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out
    })


def test_zero_token_event_does_not_trigger_kill():
    trace_id = str(uuid.uuid4())
    response = send_event(trace_id, tokens_in=0, tokens_out=0)
    assert response.json()["status"] == "ok"


def test_kill_fires_at_exact_threshold_not_later():
    trace_id = str(uuid.uuid4())
    tokens_needed_in = int(KILL_THRESHOLD / INPUT_COST_PER_TOKEN) + 10

    response = send_event(trace_id, step=0, tokens_in=max(tokens_needed_in - 1000, 0), tokens_out=0)
    assert response.json()["status"] == "ok", "Should not kill before threshold"

    response = send_event(trace_id, step=1, tokens_in=1000, tokens_out=0)
    assert response.json()["status"] == "kill", "Should kill once threshold is crossed"


def test_different_trace_ids_are_isolated():
    trace_a = str(uuid.uuid4())
    trace_b = str(uuid.uuid4())
    tokens_needed = int(KILL_THRESHOLD / INPUT_COST_PER_TOKEN) + 10

    response = send_event(trace_a, step=0, tokens_in=tokens_needed, tokens_out=0)
    assert response.json()["status"] == "kill"

    response = send_event(trace_b, step=0, tokens_in=100, tokens_out=0)
    assert response.json()["status"] == "ok", "New trace_id must start fresh, not inherit another trace's cost"


def test_output_tokens_priced_correctly():
    trace_id = str(uuid.uuid4())
    tokens_needed_out = int(KILL_THRESHOLD / OUTPUT_COST_PER_TOKEN) + 10

    response = send_event(trace_id, step=0, tokens_in=0, tokens_out=tokens_needed_out)
    assert response.json()["status"] == "kill", "Output tokens alone should trigger kill at the correct threshold"


def test_event_without_api_key_is_rejected(without_auth_override):
    """An unauthenticated event must never be recorded or evaluated for kill."""
    response = client.post("/events", json={
        "node_name": "TestNode",
        "step": 0,
        "message": "test event",
        "trace_id": str(uuid.uuid4())
    })
    assert response.status_code == 422, "Missing X-API-Key must be rejected before the handler runs"
    assert "status" not in response.json(), "Rejected request must not return a kill/ok decision"


def test_event_with_invalid_api_key_is_rejected(without_auth_override):
    response = client.post(
        "/events",
        json={
            "node_name": "TestNode",
            "step": 0,
            "message": "test event",
            "trace_id": str(uuid.uuid4())
        },
        headers={"X-API-Key": f"ag_not-a-real-key-{uuid.uuid4().hex}"}
    )
    assert response.status_code == 401
    assert "status" not in response.json(), "Rejected request must not return a kill/ok decision"
