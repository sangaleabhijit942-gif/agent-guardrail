"""
Agent Guardrail — Synthetic Test Harness (Step 1: Core Scaffold)
==================================================================

Purpose: run your existing agent graph repeatedly, in a controlled way,
with a fault-injection hook and full logging of every tool call.

Wired to the real 3-node LangGraph agent in sdk/test_agent.py via
agent_graph.stream(), which yields one step at a time — matching this
harness's per-step model. Fault injectors #1-4 will each be a small
function that plugs into `fault_fn` below.
"""

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Callable, Any

from sdk.test_agent import app as agent_graph
from agentguardrail import GuardrailKillSignal


# ---------------------------------------------------------------------------
# 1. Run configuration — what varies between test runs
# ---------------------------------------------------------------------------

@dataclass
class RunConfig:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    scenario_name: str = "baseline"          # e.g. "retry_loop", "baseline"
    fault_fn: Optional[Callable] = None      # injected in later steps
    fault_severity: float = 1.0              # 0.0 = none, 1.0 = normal, >1 = worse
    max_steps: int = 25                      # hard safety cap for the harness itself
    seed: Optional[int] = None               # for reproducibility where possible


# ---------------------------------------------------------------------------
# 2. Per-step event log — this is what your detector analysis will run on
# ---------------------------------------------------------------------------

@dataclass
class StepEvent:
    run_id: str
    step_index: int
    node_name: str                # which node in your graph (Agent/Tool/Validator)
    tool_called: Optional[str]
    tokens_used: Optional[int]
    cost_usd: Optional[float]
    timestamp: float
    injected_fault: Optional[str] # which fault (if any) was active this step
    raw_output: Any = None        # keep small — truncate large payloads before storing


class RunLog:
    """Collects StepEvents for one run and can serialize them for analysis."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.events: list[StepEvent] = []
        self.breaker_tripped: bool = False
        self.breaker_trip_step: Optional[int] = None
        self.breaker_trip_reason: Optional[str] = None
        self.started_at = time.time()
        self.ended_at: Optional[float] = None

    def record(self, event: StepEvent):
        self.events.append(event)

    def mark_tripped(self, step_index: int, reason: str):
        self.breaker_tripped = True
        self.breaker_trip_step = step_index
        self.breaker_trip_reason = reason

    def finish(self):
        self.ended_at = time.time()

    def total_cost(self) -> float:
        return sum(e.cost_usd or 0.0 for e in self.events)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "breaker_tripped": self.breaker_tripped,
            "breaker_trip_step": self.breaker_trip_step,
            "breaker_trip_reason": self.breaker_trip_reason,
            "duration_sec": (self.ended_at or time.time()) - self.started_at,
            "total_cost_usd": self.total_cost(),
            "step_count": len(self.events),
            "events": [asdict(e) for e in self.events],
        }


# ---------------------------------------------------------------------------
# 3. The harness itself — wraps the real agent graph
# ---------------------------------------------------------------------------

class TestHarness:
    """
    Wraps the real LangGraph agent (sdk/test_agent.py) so it can be run
    repeatedly with controlled fault injection and full logging.

    KNOWN GAP (documented, not yet fixed): test_agent.py's nodes call
    guardrail.track() internally to report real cost/token usage to
    ingestion-api, but that data is not currently returned in the node's
    state dict — so tokens_used/cost_usd stay None in StepEvent for now.
    Fixing this requires test_agent.py's nodes to also return cost/token
    fields in their state, not just call track() as a side effect.
    """

    def __init__(self, output_dir: str = "./test_runs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._graph_stream = None  # set fresh per run() call

    def run(self, config: RunConfig) -> RunLog:
        log = RunLog(run_id=config.run_id)

        # Start a fresh stream of the real graph for this run
        initial_state = {"step_count": 0, "message": "Start", "retry_count": 0}
        self._graph_stream = agent_graph.stream(initial_state)

        for step_index in range(config.max_steps):
            # --- Fault injection hook -------------------------------------
            # Later steps (retry-loop, malformed-call, etc.) plug in here by
            # passing a fault_fn that can modify what happens this step.
            fault_applied = None
            if config.fault_fn is not None:
                fault_applied = config.fault_fn(step_index, config.fault_severity)

            step_result = self._invoke_graph_step(step_index, fault_applied)

            if step_result is None:
                # Graph has finished naturally (StopIteration) — task complete
                break

            if step_result[0] == "GuardrailKill":
                # The real guardrail tripped inside test_agent.py's own nodes
                node_name, tool_called, tokens_used, cost_usd, raw_output = step_result
                event = StepEvent(
                    run_id=config.run_id,
                    step_index=step_index,
                    node_name=node_name,
                    tool_called=tool_called,
                    tokens_used=tokens_used,
                    cost_usd=cost_usd,
                    timestamp=time.time(),
                    injected_fault=fault_applied,
                    raw_output=raw_output,
                )
                log.record(event)
                log.mark_tripped(step_index, raw_output.get("kill_reason", "guardrail kill signal"))
                break

            node_name, tool_called, tokens_used, cost_usd, raw_output = step_result

            event = StepEvent(
                run_id=config.run_id,
                step_index=step_index,
                node_name=node_name,
                tool_called=tool_called,
                tokens_used=tokens_used,
                cost_usd=cost_usd,
                timestamp=time.time(),
                injected_fault=fault_applied,
                raw_output=raw_output,
            )
            log.record(event)

            # --- Harness-level secondary cap --------------------------------
            # Backstop only. The real guardrail threshold is enforced inside
            # test_agent.py's own nodes via guardrail.track(); this catches
            # the case where that doesn't fire for some reason.
            tripped, reason = self._check_circuit_breaker(log)
            if tripped:
                log.mark_tripped(step_index, reason)
                break

        log.finish()
        self._save(log)
        return log

    # -----------------------------------------------------------------
    # Real graph invocation — pulls from the live LangGraph stream
    # -----------------------------------------------------------------

    def _invoke_graph_step(self, step_index: int, fault_applied: Optional[str]):
        """
        Pulls one real step from the live LangGraph stream.
        Returns None when the graph has finished (StopIteration).
        Returns a ("GuardrailKill", ...) tuple if the real guardrail
        threshold tripped inside test_agent.py's nodes.
        """
        try:
            chunk = next(self._graph_stream)
        except StopIteration:
            return None
        except GuardrailKillSignal as e:
            return ("GuardrailKill", None, None, None, {"kill_reason": str(e)})

        # chunk is a dict like {"agent": {...state...}} or {"validator": {...}}
        node_name = list(chunk.keys())[0]
        node_state = chunk[node_name]

        return (
            node_name,
            None,  # tool_called — not tracked per-node in current test_agent.py
            None,  # tokens_used — see class docstring: not yet surfaced from track()
            None,  # cost_usd    — see class docstring: not yet surfaced from track()
            node_state,
        )

    def _check_circuit_breaker(self, log: RunLog) -> tuple[bool, Optional[str]]:
        """
        Harness-level secondary cap only — see run()'s comment above this
        call. The real enforcement is the guardrail's own threshold, caught
        via GuardrailKillSignal in _invoke_graph_step.
        """
        SIMPLE_BUDGET_CAP = 5.00  # placeholder — real check happens elsewhere
        if log.total_cost() > SIMPLE_BUDGET_CAP:
            return True, f"harness-level budget cap exceeded (${log.total_cost():.4f})"
        return False, None

    def _task_complete(self, raw_output: Any) -> bool:
        """STUB: replace with your real 'is the task actually done' check."""
        return False  # keep running until max_steps, natural StopIteration, or kill

    # -----------------------------------------------------------------

    def _save(self, log: RunLog):
        path = self.output_dir / f"{log.run_id}.json"
        with open(path, "w") as f:
            json.dump(log.to_dict(), f, indent=2)


# ---------------------------------------------------------------------------
# 4. Minimal smoke test — proves the scaffold runs end-to-end against the
#    real agent graph (this makes REAL Anthropic API calls and REAL
#    guardrail.track() calls to ingestion-api — not free, not simulated)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    harness = TestHarness()
    config = RunConfig(scenario_name="baseline_smoke_test")
    result = harness.run(config)

    print(f"Run {result.run_id} finished:")
    print(f"  steps executed: {len(result.events)}")
    print(f"  total cost: ${result.total_cost():.4f}")
    print(f"  breaker tripped: {result.breaker_tripped}")
    if result.breaker_tripped:
        print(f"  tripped at step {result.breaker_trip_step}: {result.breaker_trip_reason}")
    print(f"  full log saved to: test_runs/{result.run_id}.json")