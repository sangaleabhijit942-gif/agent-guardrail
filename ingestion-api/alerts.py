"""
Graduated, pattern-aware alerts — not static 50/80/95% checkpoints, but a
per-workflow estimate of calls remaining, based on that workflow's own
recent token usage rate. Deliberately separate from the kill path: this
is informational only and never affects the kill decision itself.
"""


def check_graduated_alert(client, trace_id: str, customer_id: str, current_value: float, limit: float) -> dict | None:
    if limit <= 0:
        return None

    pct_used = current_value / limit
    if pct_used < 0.5:
        return None  # sगgyat कमी tier च्या खाली, अजून काही सांगायची गरज नाही

    result = client.query(
        """
        SELECT tokens_in FROM agent_events
        WHERE trace_id = {t:String} AND customer_id = {c:String}
        ORDER BY timestamp ASC
        """,
        parameters={"t": trace_id, "c": customer_id}
    )
    token_sizes = [row[0] for row in result.result_rows if row[0] and row[0] > 0]

    if not token_sizes:
        return None

    recent_window = token_sizes[-3:] if len(token_sizes) >= 3 else token_sizes
    avg_recent = sum(recent_window) / len(recent_window)

    remaining_budget = limit - current_value
    estimated_calls_left = max(0, int(remaining_budget / avg_recent)) if avg_recent > 0 else None

    if pct_used >= 0.95:
        severity = "critical"
    elif pct_used >= 0.80:
        severity = "warning"
    else:
        severity = "notice"

    return {
        "severity": severity,
        "pct_used": round(pct_used * 100, 1),
        "estimated_calls_remaining": estimated_calls_left,
        "recent_avg_tokens_per_call": round(avg_recent, 1)
    }