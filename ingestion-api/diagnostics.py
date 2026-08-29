from fastapi import APIRouter, Depends
from clickhouse_client import get_client
from auth import get_current_customer

router = APIRouter()


def classify_retry_pattern(intervals: list) -> dict:
    """
    Classify why repeated calls are happening, based purely on timing intervals
    between events. Uses no customer code or content — only timestamps already stored.
    """
    if len(intervals) < 3:
        return {"pattern": "insufficient_data", "confidence": "none", "description": "Not enough repeated calls to classify reliably."}

    avg = sum(intervals) / len(intervals)

    if all(i < 1.0 for i in intervals):
        return {
            "pattern": "tight_loop",
            "confidence": "high",
            "description": "All calls arriving within a second of each other. Consistent with a loop retrying immediately, often where an error is being caught and ignored."
        }

    is_monotonic_growth = all(
        intervals[i] >= intervals[i - 1] * 1.5
        for i in range(1, len(intervals))
    )
    if is_monotonic_growth:
        return {
            "pattern": "exponential_backoff",
            "confidence": "high",
            "description": "Intervals between calls increase geometrically with each attempt. Consistent with automatic retry logic in an HTTP client or agent framework."
        }

    variance = sum((i - avg) ** 2 for i in intervals) / len(intervals)
    std_dev = variance ** 0.5
    if avg > 10 and std_dev < avg * 0.15:
        return {
            "pattern": "periodic_restart",
            "confidence": "medium",
            "description": f"Calls arriving at a consistent ~{int(avg)}s interval. Consistent with a process being restarted on a schedule, such as by a supervisor or scheduler."
        }

    return {
        "pattern": "irregular",
        "confidence": "low",
        "description": "Repeated calls detected, but the timing does not match a known automated retry signature. This may indicate manual runs, variable workload, or a pattern not yet recognised."
    }


@router.get("/diagnostics/{trace_id}")
async def get_trace_diagnostics(trace_id: str, customer_id: str = Depends(get_current_customer)):
    client = get_client()

    result = client.query(
        """
        SELECT timestamp, node_name, message
        FROM agent_events
        WHERE trace_id = {trace_id:String} AND customer_id = {cust:String}
        ORDER BY timestamp ASC
        """,
        parameters={"trace_id": trace_id, "cust": customer_id}
    )

    rows = result.result_rows
    if len(rows) < 2:
        return {
            "trace_id": trace_id,
            "event_count": len(rows),
            "analysis": {"pattern": "insufficient_data", "confidence": "none", "description": "Not enough events to analyze."}
        }

    timestamps = [row[0] for row in rows]
    intervals = [
        (timestamps[i] - timestamps[i - 1]).total_seconds()
        for i in range(1, len(timestamps))
    ]

    analysis = classify_retry_pattern(intervals)

    return {
        "trace_id": trace_id,
        "event_count": len(rows),
        "first_event": timestamps[0].isoformat(),
        "last_event": timestamps[-1].isoformat(),
        "duration_seconds": round((timestamps[-1] - timestamps[0]).total_seconds(), 2),
        "intervals_seconds": [round(i, 3) for i in intervals],
        "analysis": analysis
    }
