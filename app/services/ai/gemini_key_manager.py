"""
Manages rotation across multiple Gemini API keys. This is a pool that
looks like a single provider from the outside (same generate/generate_json/
stream/analyze interface) but internally tries each key in order,
skipping keys currently in cooldown, and only raises up to
AIProviderManager once every key has been exhausted for this request —
at which point the manager falls through to the next provider in
AI_PROVIDER_ORDER (e.g. Groq).

State is kept in-process (per Flask worker). That's a known limitation for
multi-worker/multi-process deployments — see the note in provider_manager.py
— but is intentional for this phase: moving it to Redis/DB is a drop-in
swap of _KeyState storage later without changing the rotation algorithm.
"""

import threading
import time
from dataclasses import dataclass
from typing import Optional

from app.services.ai.base_provider import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTransientError,
)
from app.services.ai.gemini_provider import GeminiProvider

DEFAULT_COOLDOWN_SECONDS = 60


@dataclass
class _KeyState:
    key: str
    request_count: int = 0
    failure_count: int = 0
    rate_limit_count: int = 0
    cooldown_until: float = 0.0
    last_success_at: Optional[float] = None

    def is_available(self) -> bool:
        return time.monotonic() >= self.cooldown_until


class GeminiKeyManager:
    """Duck-types the same interface as BaseAIProvider (generate,
    generate_json, stream, analyze) so AIProviderManager can treat it
    exactly like a single provider."""

    name = "gemini"

    def __init__(self, api_keys, model, cooldown_seconds=DEFAULT_COOLDOWN_SECONDS, timeout=30):
        if not api_keys:
            raise ValueError("GeminiKeyManager requires at least one API key.")
        self.model = model
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._states = {key: _KeyState(key=key) for key in api_keys}
        self._key_order = list(api_keys)  # fixed order — round robin, not random
        self._next_index = 0
        self._providers = {key: GeminiProvider(api_key=key, model=model, timeout=timeout) for key in api_keys}

    # --- Rotation bookkeeping -------------------------------------------------
    def _pick_next_key(self):
        """Round-robin starting from _next_index, skipping keys in cooldown."""
        with self._lock:
            n = len(self._key_order)
            for offset in range(n):
                idx = (self._next_index + offset) % n
                key = self._key_order[idx]
                if self._states[key].is_available():
                    self._next_index = (idx + 1) % n
                    return key
            return None  # every key is in cooldown

    def _record_success(self, key):
        with self._lock:
            state = self._states[key]
            state.request_count += 1
            state.last_success_at = time.monotonic()

    def _record_rate_limit(self, key):
        with self._lock:
            state = self._states[key]
            state.request_count += 1
            state.rate_limit_count += 1
            state.cooldown_until = time.monotonic() + self.cooldown_seconds

    def _record_failure(self, key, cooldown=False):
        with self._lock:
            state = self._states[key]
            state.request_count += 1
            state.failure_count += 1
            if cooldown:
                state.cooldown_until = time.monotonic() + self.cooldown_seconds

    def stats(self):
        """For the admin panel (Phase 13) — never exposes the raw key."""
        with self._lock:
            return [
                {
                    "key_suffix": state.key[-4:] if len(state.key) >= 4 else "****",
                    "requests": state.request_count,
                    "failures": state.failure_count,
                    "rate_limit_events": state.rate_limit_count,
                    "in_cooldown": not state.is_available(),
                    "last_success_at": state.last_success_at,
                }
                for state in self._states.values()
            ]

    # --- Provider-shaped interface --------------------------------------------
    def _with_key_rotation(self, method_name, *args, **kwargs):
        attempts = 0
        max_attempts = len(self._key_order)
        last_error = None

        while attempts < max_attempts:
            key = self._pick_next_key()
            if key is None:
                break  # all keys in cooldown

            provider = self._providers[key]
            method = getattr(provider, method_name)
            try:
                result = method(*args, **kwargs)
                self._record_success(key)
                return result
            except ProviderRateLimitError as exc:
                self._record_rate_limit(key)
                last_error = exc
            except ProviderTransientError as exc:
                self._record_failure(key, cooldown=False)
                last_error = exc
            except ProviderAuthError as exc:
                # This specific key is misconfigured — cool it down so we
                # don't keep hammering a dead key, and try the next one.
                self._record_failure(key, cooldown=True)
                last_error = exc

            attempts += 1

        if last_error is not None:
            raise last_error
        raise ProviderRateLimitError("All Gemini API keys are currently in cooldown.")

    def generate(self, prompt, **kwargs):
        return self._with_key_rotation("generate", prompt, **kwargs)

    def generate_json(self, prompt, **kwargs):
        return self._with_key_rotation("generate_json", prompt, **kwargs)

    def analyze(self, context, question, **kwargs):
        return self._with_key_rotation("analyze", context, question, **kwargs)

    def stream(self, prompt, **kwargs):
        # Streaming mid-flight failures aren't retried key-to-key (a partial
        # stream can't be "resumed" on another key) — pick one available key
        # and stream from it; a failure here surfaces directly to the caller.
        key = self._pick_next_key()
        if key is None:
            raise ProviderRateLimitError("All Gemini API keys are currently in cooldown.")
        provider = self._providers[key]
        try:
            yield from provider.stream(prompt, **kwargs)
            self._record_success(key)
        except (ProviderRateLimitError, ProviderTransientError, ProviderAuthError):
            self._record_failure(key, cooldown=True)
            raise
