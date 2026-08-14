"""
In-memory response cache keyed by a deterministic hash of
(provider, model, prompt, context). Same request repeated -> cached
response, reducing API usage/cost/latency (spec section 22).

Like GeminiKeyManager's rotation state, this is per-process. Swapping to
Redis later is a matter of replacing the dict in InMemoryResponseCache
with a Redis-backed get/set — the hashing and TTL logic don't change.
"""

import hashlib
import json
import threading
import time


def build_cache_key(provider: str, model: str, prompt: str, context: dict = None) -> str:
    payload = {
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "context": context or {},
    }
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class InMemoryResponseCache:
    def __init__(self, default_ttl_seconds: int = 3600):
        self.default_ttl_seconds = default_ttl_seconds
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value, ttl_seconds: int = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
