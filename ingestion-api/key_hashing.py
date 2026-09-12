"""
Small helper for hashing API keys before storing/comparing them.
SHA-256 is one-way: the raw key can never be recovered from the hash,
so a database leak does not expose customer keys.
"""
import hashlib

def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()