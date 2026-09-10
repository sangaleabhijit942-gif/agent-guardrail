"""
In-memory TTL cache for API-key -> customer_id auth lookups.

Exists to avoid a ClickHouse round-trip on every single request. Only
successful lookups are ever cached; a failed lookup must fail closed and
never fall back to a stale or unrelated cache entry (enforced by callers
in auth.py, not here).
"""
import threading
import time

AUTH_CACHE_TTL_SECONDS = 45

_cache: dict[str, tuple[str, float]] = {}
_lock = threading.Lock()


def get_cached_customer_id(api_key: str) -> str | None:
    with _lock:
        entry = _cache.get(api_key)
        if entry is None:
            return None
        customer_id, expires_at = entry
        if time.monotonic() >= expires_at:
            del _cache[api_key]
            return None
        return customer_id


def set_cached_customer_id(api_key: str, customer_id: str) -> None:
    with _lock:
        _cache[api_key] = (customer_id, time.monotonic() + AUTH_CACHE_TTL_SECONDS)
