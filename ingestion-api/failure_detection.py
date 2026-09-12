"""
Shared logic for detecting a workflow stuck in a consecutive-failure loop,
independent of cost/token thresholds. Used by both the kill path (events.py)
and reporting (reporting.py) so a workflow killed this way shows correctly
as "killed" everywhere, not just in the one-off /events response.
"""
from config import MAX_CONSECUTIVE_FAILURES


def consecutive_failures_exceeded(trace_id: str, customer_id: str, client) -> bool:
    result = client.query(
        """
        SELECT tokens_out
        FROM agent_events
        WHERE trace_id = {trace_id:String} AND customer_id = {cust:String}
        ORDER BY timestamp DESC
        LIMIT {n:UInt32}
        """,
        parameters={"trace_id": trace_id, "cust": customer_id, "n": MAX_CONSECUTIVE_FAILURES}
    )
    rows = result.result_rows
    if len(rows) < MAX_CONSECUTIVE_FAILURES:
        return False
    return all(row[0] == 0 for row in rows)