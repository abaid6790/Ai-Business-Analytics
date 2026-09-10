"""
Response cache keyed by a deterministic hash of (provider, model, prompt,
context). Same request repeated -> cached response, reducing API usage/
cost/latency (spec section 22).

Two implementations behind the same get/set/clear interface:
  - InMemoryResponseCache: per-process, zero setup. Under multiple gunicorn
    workers each worker has its own cache — correct, just not coordinated.
  - RedisResponseCache: shared across every worker/container. Used
    automatically when REDIS_URL is configured (see app/services/ai/__init__.py).
"""

import hashlib
import json
import pickle
import threading
import time

CACHE_KEY_PREFIX = "ai_cache:"


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


class RedisResponseCache:
    """
    Values (ProviderResponse objects) are pickled — this is safe here
    specifically because this Redis keyspace is write-only by this
    application's own code (the AI layer), never by anything accepting
    external/untrusted input, so there's no untrusted-deserialization risk
    the way there would be if user-supplied data ever reached this pickle.
    """

    def __init__(self, redis_client, default_ttl_seconds: int = 3600, key_prefix: str = CACHE_KEY_PREFIX):
        self._client = redis_client
        self.default_ttl_seconds = default_ttl_seconds
        self._key_prefix = key_prefix

    def _full_key(self, key: str) -> str:
        return f"{self._key_prefix}{key}"

    def get(self, key: str):
        raw = self._client.get(self._full_key(key))
        if raw is None:
            return None
        try:
            return pickle.loads(raw)
        except Exception:
            return None  # corrupted/incompatible entry — treat as a miss, not a crash

    def set(self, key: str, value, ttl_seconds: int = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        self._client.set(self._full_key(key), pickle.dumps(value), ex=ttl)

    def clear(self) -> None:
        prefix = f"{self._key_prefix}*"
        for redis_key in self._client.scan_iter(match=prefix):
            self._client.delete(redis_key)
