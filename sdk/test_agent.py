from typing import TypedDict
from langgraph.graph import StateGraph, START, END
import time
from dotenv import load_dotenv
import os
import anthropic
from agentguardrail import GuardrailClient, GuardrailKillSignal

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

guardrail = GuardrailClient(
    api_key="ag_test_51f8a3c2e94b4d7a9c1f6e8b2a3d5c7f",
    workflow_name="test-agent-workflow",
    timeout=15
)

class AgentState(TypedDict):
    step_count: int
    message: str
    retry_count: int

def agent_node(state: AgentState) -> AgentState:
    guardrail.track("Agent", state["step_count"], "Calling fake tool...")
    return {
        "step_count": state["step_count"] + 1,
        "message": "Calling fake tool...",
        "retry_count": state["retry_count"]
    }

def fake_tool_node(state: AgentState) -> AgentState:
    guardrail.track("Fake Tool", state["step_count"], "Executing fake tool action...")
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

    guardrail.track("Validator", state["step_count"], "Validating tool result...", tokens_in, tokens_out)

    if "FAIL" in decision and state["retry_count"] < 2:
        guardrail.track("Validator", state["step_count"], "Validation FAILED (LLM decision) — flagging retry")
        return {
            "step_count": state["step_count"],
            "message": "Validation failed, retrying...",
            "retry_count": state["retry_count"] + 1
        }

    guardrail.track("Validator", state["step_count"], "Validation passed")
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
    print(f"=== Starting Local Agent Execution (trace_id: {guardrail.trace_id}) ===")
    initial_state = {"step_count": 0, "message": "Start", "retry_count": 0}
    try:
        result = app.invoke(initial_state)
        print("\n=== Execution Complete ===")
        print("Final State Output:", result)
    except GuardrailKillSignal as e:
        print(f"\n[STOPPED BY GUARDRAIL] Reason: {e}")