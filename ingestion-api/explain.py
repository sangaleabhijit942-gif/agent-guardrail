"""
Optional, separate from the kill path. Calls Claude to turn the rule-based
diagnosis into a natural-language, actionable explanation. Never called
automatically during a kill — customer requests this separately, after
the fact, if they want more detail than the rule-based diagnosis gives.
"""
from fastapi import APIRouter, Depends, HTTPException
import anthropic
import os
from clickhouse_client import get_client
from auth import get_current_customer
from diagnostics import classify_retry_pattern, classify_token_growth

router = APIRouter()

_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="Explanation feature not configured on this server.")
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
    return _anthropic_client


@router.get("/explain/{trace_id}")
async def explain_trace(trace_id: str, customer_id: str = Depends(get_current_customer)):
    client = get_client()

    result = client.query(
        """
        SELECT timestamp, node_name, message, tokens_in, tokens_out
        FROM agent_events
        WHERE trace_id = {trace_id:String} AND customer_id = {cust:String}
        ORDER BY timestamp ASC
        """,
        parameters={"trace_id": trace_id, "cust": customer_id}
    )
    rows = result.result_rows
    if len(rows) < 2:
        return {"trace_id": trace_id, "explanation": "Not enough events on this trace to explain."}

    timestamps = [row[0] for row in rows]
    intervals = [(timestamps[i] - timestamps[i - 1]).total_seconds() for i in range(1, len(timestamps))]
    events_with_tokens = [(row[1], row[3]) for row in rows]

    diagnosis = classify_token_growth(events_with_tokens)
    if diagnosis is None:
        diagnosis = classify_retry_pattern(intervals)

    # Only node names, timings, and token counts go to Claude — never
    # the customer's actual message content, which we never store anyway.
    summary_lines = [
        f"Event {i}: node='{row[1]}', tokens_in={row[3]}, tokens_out={row[4]}"
        for i, row in enumerate(rows)
    ]
    event_summary = "\n".join(summary_lines)

    prompt = f"""A customer's AI agent workflow was stopped by a cost-governance tool.
Here is the rule-based diagnosis and the raw event data (node names and token
counts only — no actual message content):

Rule-based diagnosis: {diagnosis['pattern']} (confidence: {diagnosis['confidence']})
Rule-based description: {diagnosis['description']}

Event sequence:
{event_summary}

In 2-3 short, plain-language sentences, explain to a developer what likely
happened and suggest one concrete next step. Do not invent details not
supported by the data above. If the rule-based diagnosis is 'irregular' or
'insufficient_data', say honestly that the cause isn't clear from this data
alone rather than guessing."""

    try:
        anthropic_client = _get_anthropic_client()
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        explanation_text = response.content[0].text
    except Exception as e:
        return {
            "trace_id": trace_id,
            "rule_based_diagnosis": diagnosis,
            "explanation": f"AI explanation unavailable ({e}). Rule-based diagnosis above still applies."
        }

    return {
        "trace_id": trace_id,
        "rule_based_diagnosis": diagnosis,
        "explanation": explanation_text
    }