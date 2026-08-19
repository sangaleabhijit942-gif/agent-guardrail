from typing import TypedDict
from langgraph.graph import StateGraph, START, END
import time
import requests

INGESTION_URL = "http://localhost:8000/events"

def send_trace_event(node_name: str, step: int, message: str):
    try:
        requests.post(INGESTION_URL, json={
            "node_name": node_name,
            "step": step,
            "message": message
        }, timeout=1)
    except requests.exceptions.RequestException as e:
        print(f"[WARN] Failed to send trace event: {e}")

# 1. Define State
class AgentState(TypedDict):
    step_count: int
    message: str
    retry_count: int

# 2. Node 1: Agent Step
def agent_node(state: AgentState) -> AgentState:
    send_trace_event("Agent", state["step_count"], "Calling fake tool...")
    return {
        "step_count": state["step_count"] + 1,
        "message": "Calling fake tool...",
        "retry_count": state["retry_count"]
    }

# 3. Node 2: Fake Tool
def fake_tool_node(state: AgentState) -> AgentState:
    send_trace_event("Fake Tool", state["step_count"], "Executing fake tool action...")
    time.sleep(0.3)
    return {
        "step_count": state["step_count"],
        "message": "Tool executed successfully.",
        "retry_count": state["retry_count"]
    }

# 4. Node 3: Validator — checks the tool's result, decides proceed or retry
def validator_node(state: AgentState) -> AgentState:
    send_trace_event("Validator", state["step_count"], "Validating tool result...")
    time.sleep(0.2)
    # Simple simulated check: fail validation once (on step 1) to force a retry, pass otherwise
    if state["step_count"] == 1 and state["retry_count"] == 0:
        send_trace_event("Validator", state["step_count"], "Validation FAILED — flagging retry")
        return {
            "step_count": state["step_count"],
            "message": "Validation failed, retrying...",
            "retry_count": state["retry_count"] + 1
        }
    send_trace_event("Validator", state["step_count"], "Validation passed")
    return {
        "step_count": state["step_count"],
        "message": "Validation passed",
        "retry_count": state["retry_count"]
    }

# 5. Conditional Edge from Agent (loop 3 times then stop)
def should_continue(state: AgentState) -> str:
    if state["step_count"] < 3:
        return "call_tool"
    return "stop"

# 6. Conditional Edge from Validator (retry tool or move back to agent)
def validation_result(state: AgentState) -> str:
    if state["message"] == "Validation failed, retrying...":
        return "retry"
    return "proceed"

# 7. Build Graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("fake_tool", fake_tool_node)
workflow.add_node("validator", validator_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "call_tool": "fake_tool",
        "stop": END
    }
)
workflow.add_edge("fake_tool", "validator")
workflow.add_conditional_edges(
    "validator",
    validation_result,
    {
        "retry": "fake_tool",
        "proceed": "agent"
    }
)

app = workflow.compile()

# 8. Execute Locally
if __name__ == "__main__":
    print("=== Starting Local Agent Execution ===")
    initial_state = {"step_count": 0, "message": "Start", "retry_count": 0}
    result = app.invoke(initial_state)
    print("\n=== Execution Complete ===")
    print("Final State Output:", result)