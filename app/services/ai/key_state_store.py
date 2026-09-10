"""
Pluggable storage for Gemini key-rotation state (request/failure/rate-limit
counts, cooldown timers, round-robin position). GeminiKeyManager delegates
all bookkeeping here so the rotation *algorithm* never has to know whether
it's running in-process or shared across workers via Redis.

Both implementations use wall-clock time (time.time()), not
time.monotonic() — monotonic time is only meaningful within one process's
uptime, so a cooldown timestamp written by one worker would be
meaningless to another worker reading it. Wall-clock is the only choice
that's comparable across processes and survives a restart.
"""

import hashlib
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class KeyStats:
    key_suffix: str
    requests: int
    failures: int
    rate_limit_events: int
    in_cooldown: bool
    last_success_at: Optional[float]

    def as_dict(self) -> dict:
        return {
            "key_suffix": self.key_suffix,
            "requests": self.requests,
            "failures": self.failures,
            "rate_limit_events": self.rate_limit_events,
            "in_cooldown": self.in_cooldown,
            "last_success_at": self.last_success_at,
        }


class KeyStateStore(ABC):
    @abstractmethod
    def pick_next_key(self, key_order: list) -> Optional[str]:
        """Round-robin (never random) among `key_order`, skipping any key
        currently in cooldown. Returns None if every key is in cooldown."""

    @abstractmethod
    def record_success(self, key: str) -> None: ...

    @abstractmethod
    def record_rate_limit(self, key: str, cooldown_seconds: int) -> None: ...

    @abstractmethod
    def record_failure(self, key: str, cooldown: bool, cooldown_seconds: int) -> None: ...

    @abstractmethod
    def get_stats(self, key_order: list) -> list:
        """Returns a list of dicts, one per key — never includes the raw
        key, only a 4-character suffix, for the admin panel."""


def _key_suffix(key: str) -> str:
    return key[-4:] if len(key) >= 4 else "****"


# ---------------------------------------------------------------------------
# In-process implementation (default — zero setup, per-worker only)
# ---------------------------------------------------------------------------
@dataclass
class _InMemoryKeyState:
    key: str
    request_count: int = 0
    failure_count: int = 0
    rate_limit_count: int = 0
    cooldown_until: float = 0.0
    last_success_at: Optional[float] = None

    def is_available(self) -> bool:
        return time.time() >= self.cooldown_until


class InMemoryKeyStateStore(KeyStateStore):
    def __init__(self, api_keys: list):
        self._lock = threading.Lock()
        self._states = {key: _InMemoryKeyState(key=key) for key in api_keys}
        self._next_index = 0

    def pick_next_key(self, key_order: list) -> Optional[str]:
        with self._lock:
            n = len(key_order)
            for offset in range(n):
                idx = (self._next_index + offset) % n
                key = key_order[idx]
                if self._states[key].is_available():
                    self._next_index = (idx + 1) % n
                    return key
            return None

    def record_success(self, key: str) -> None:
        with self._lock:
            state = self._states[key]
            state.request_count += 1
            state.last_success_at = time.time()

    def record_rate_limit(self, key: str, cooldown_seconds: int) -> None:
        with self._lock:
            state = self._states[key]
            state.request_count += 1
            state.rate_limit_count += 1
            state.cooldown_until = time.time() + cooldown_seconds

    def record_failure(self, key: str, cooldown: bool, cooldown_seconds: int) -> None:
        with self._lock:
            state = self._states[key]
            state.request_count += 1
            state.failure_count += 1
            if cooldown:
                state.cooldown_until = time.time() + cooldown_seconds

    def get_stats(self, key_order: list) -> list:
        with self._lock:
            return [
                KeyStats(
                    key_suffix=_key_suffix(state.key),
                    requests=state.request_count,
                    failures=state.failure_count,
                    rate_limit_events=state.rate_limit_count,
                    in_cooldown=not state.is_available(),
                    last_success_at=state.last_success_at,
                ).as_dict()
                for key in key_order
                for state in [self._states[key]]
            ]


# ---------------------------------------------------------------------------
# Redis implementation (shared across every worker/container)
# ---------------------------------------------------------------------------
class RedisKeyStateStore(KeyStateStore):
    """
    Each key's counters live in a Redis hash, keyed by a hash of the API
    key (never the raw key itself, so it never appears in a `KEYS`/`SCAN`
    listing even to someone with Redis access). Round-robin position is a
    single shared counter (INCR), so requests fan out across keys evenly
    across every worker, not just within one.

    This isn't wrapped in a Lua script for strict atomicity — the only
    race this allows is two workers picking the same (not-in-cooldown) key
    at the same moment, which is harmless: keys are meant to serve
    concurrent requests anyway. Cooldown only prevents *repeatedly*
    targeting an already-failing key, and that guarantee still holds.
    """

    def __init__(self, redis_client, pool_namespace: str = "gemini_keys"):
        self._client = redis_client
        self._ns = pool_namespace

    def _hash_key(self, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return f"{self._ns}:state:{digest}"

    def _counter_key(self) -> str:
        return f"{self._ns}:rr_index"

    def pick_next_key(self, key_order: list) -> Optional[str]:
        n = len(key_order)
        start = self._client.incr(self._counter_key())
        for offset in range(n):
            idx = (start + offset) % n
            key = key_order[idx]
            cooldown_until = self._client.hget(self._hash_key(key), "cooldown_until")
            cooldown_until = float(cooldown_until) if cooldown_until else 0.0
            if time.time() >= cooldown_until:
                return key
        return None

    def record_success(self, key: str) -> None:
        redis_key = self._hash_key(key)
        pipe = self._client.pipeline()
        pipe.hincrby(redis_key, "request_count", 1)
        pipe.hset(redis_key, "last_success_at", time.time())
        pipe.execute()

    def record_rate_limit(self, key: str, cooldown_seconds: int) -> None:
        redis_key = self._hash_key(key)
        pipe = self._client.pipeline()
        pipe.hincrby(redis_key, "request_count", 1)
        pipe.hincrby(redis_key, "rate_limit_count", 1)
        pipe.hset(redis_key, "cooldown_until", time.time() + cooldown_seconds)
        pipe.execute()

    def record_failure(self, key: str, cooldown: bool, cooldown_seconds: int) -> None:
        redis_key = self._hash_key(key)
        pipe = self._client.pipeline()
        pipe.hincrby(redis_key, "request_count", 1)
        pipe.hincrby(redis_key, "failure_count", 1)
        if cooldown:
            pipe.hset(redis_key, "cooldown_until", time.time() + cooldown_seconds)
        pipe.execute()

    def get_stats(self, key_order: list) -> list:
        results = []
        now = time.time()
        for key in key_order:
            data = self._client.hgetall(self._hash_key(key))
            data = {
                (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
                for k, v in data.items()
            }
            cooldown_until = float(data.get("cooldown_until", 0) or 0)
            last_success_raw = data.get("last_success_at")
            results.append(KeyStats(
                key_suffix=_key_suffix(key),
                requests=int(data.get("request_count", 0) or 0),
                failures=int(data.get("failure_count", 0) or 0),
                rate_limit_events=int(data.get("rate_limit_count", 0) or 0),
                in_cooldown=now < cooldown_until,
                last_success_at=float(last_success_raw) if last_success_raw else None,
            ).as_dict())
        return results
