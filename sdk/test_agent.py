from typing import TypedDict
from langgraph.graph import StateGraph, START, END
import time
import requests
import uuid
from dotenv import load_dotenv
import os
import anthropic

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

INGESTION_URL = "http://localhost:8000/events"
TRACE_ID = str(uuid.uuid4())
WORKFLOW_NAME = "test-agent-workflow"
API_KEY = "ag_test_51f8a3c2e94b4d7a9c1f6e8b2a3d5c7f"

def send_trace_event(node_name: str, step: int, message: str, tokens_in: int = 0, tokens_out: int = 0) -> dict:
    try:
        response = requests.post(
            INGESTION_URL,
            json={
                "node_name": node_name,
                "step": step,
                "message": message,
                "trace_id": TRACE_ID,
                "workflow_name": WORKFLOW_NAME,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out
            },
            headers={"X-API-Key": API_KEY},
            timeout=5
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[WARN] Failed to send trace event: {e}")
        return {"status": "ok"}

class AgentState(TypedDict):
    step_count: int
    message: str
    retry_count: int

def agent_node(state: AgentState) -> AgentState:
    result = send_trace_event("Agent", state["step_count"], "Calling fake tool...")
    if result.get("status") == "kill":
        print(f"\n[STOPPED BY GUARDRAIL] Reason: {result.get('reason')}")
        raise RuntimeError("Workflow killed by cost guardrail")
    return {
        "step_count": state["step_count"] + 1,
        "message": "Calling fake tool...",
        "retry_count": state["retry_count"]
    }

def fake_tool_node(state: AgentState) -> AgentState:
    result = send_trace_event("Fake Tool", state["step_count"], "Executing fake tool action...")
    if result.get("status") == "kill":
        print(f"\n[STOPPED BY GUARDRAIL] Reason: {result.get('reason')}")
        raise RuntimeError("Workflow killed by cost guardrail")
    time.sleep(0.3)
    return {
        "step_count": state["step_count"],
        "message": "Tool executed successfully.",
        "retry_count": state["retry_count"]
    }

def validator_node(state: AgentState) -> AgentState:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": f"You are validating a tool's output on step {state['step_count']} of an automated workflow, retry attempt {state['retry_count']}. Respond with exactly one word: PASS or FAIL. Randomly decide, as if judging a real but unseen tool result."
        }]
    )
    decision = response.content[0].text.strip().upper()
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    print(f"[LLM DECISION] {decision} (tokens: {tokens_in} in / {tokens_out} out)")

    result = send_trace_event("Validator", state["step_count"], "Validating tool result...", tokens_in, tokens_out)
    if result.get("status") == "kill":
        print(f"\n[STOPPED BY GUARDRAIL] Reason: {result.get('reason')}")
        raise RuntimeError("Workflow killed by cost guardrail")

    if "FAIL" in decision and state["retry_count"] < 2:
        result = send_trace_event("Validator", state["step_count"], "Validation FAILED (LLM decision) — flagging retry")
        if result.get("status") == "kill":
            print(f"\n[STOPPED BY GUARDRAIL] Reason: {result.get('reason')}")
            raise RuntimeError("Workflow killed by cost guardrail")
        return {
            "step_count": state["step_count"],
            "message": "Validation failed, retrying...",
            "retry_count": state["retry_count"] + 1
        }

    result = send_trace_event("Validator", state["step_count"], "Validation passed")
    if result.get("status") == "kill":
        print(f"\n[STOPPED BY GUARDRAIL] Reason: {result.get('reason')}")
        raise RuntimeError("Workflow killed by cost guardrail")
    return {
        "step_count": state["step_count"],
        "message": "Validation passed",
        "retry_count": state["retry_count"]
    }

def should_continue(state: AgentState) -> str:
    if state["step_count"] < 3:
        return "call_tool"
    return "stop"

def validation_result(state: AgentState) -> str:
    if state["message"] == "Validation failed, retrying...":
        return "retry"
    return "proceed"

workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("fake_tool", fake_tool_node)
workflow.add_node("validator", validator_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {"call_tool": "fake_tool", "stop": END}
)
workflow.add_edge("fake_tool", "validator")
workflow.add_conditional_edges(
    "validator",
    validation_result,
    {"retry": "fake_tool", "proceed": "agent"}
)

app = workflow.compile()

if __name__ == "__main__":
    print(f"=== Starting Local Agent Execution (trace_id: {TRACE_ID}) ===")
    initial_state = {"step_count": 0, "message": "Start", "retry_count": 0}
    try:
        result = app.invoke(initial_state)
        print("\n=== Execution Complete ===")
        print("Final State Output:", result)
    except RuntimeError as e:
        print(f"\n=== Execution Halted: {e} ===")