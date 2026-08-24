from fastapi.testclient import TestClient
from main import app, ch_client, KILL_THRESHOLD, INPUT_COST_PER_TOKEN, OUTPUT_COST_PER_TOKEN
import pytest
import uuid

client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup_test_events():
    yield
    ch_client.command("TRUNCATE TABLE agent_events")

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