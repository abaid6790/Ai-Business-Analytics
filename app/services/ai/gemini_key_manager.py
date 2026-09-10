"""
Manages rotation across multiple Gemini API keys. This is a pool that
looks like a single provider from the outside (same generate/generate_json/
stream/analyze interface) but internally tries each key in order,
skipping keys currently in cooldown, and only raises up to
AIProviderManager once every key has been exhausted for this request —
at which point the manager falls through to the next provider in
AI_PROVIDER_ORDER (e.g. Groq).

Rotation state (request/failure counts, cooldown timers, round-robin
position) is delegated to a pluggable KeyStateStore — InMemoryKeyStateStore
by default (per-worker, zero setup), or RedisKeyStateStore when REDIS_URL
is configured (shared across every worker/container). The rotation
*algorithm* here never changes based on which one is in use.
"""

from app.services.ai.base_provider import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTransientError,
)
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.key_state_store import InMemoryKeyStateStore

DEFAULT_COOLDOWN_SECONDS = 60


class GeminiKeyManager:
    """Duck-types the same interface as BaseAIProvider (generate,
    generate_json, stream, analyze) so AIProviderManager can treat it
    exactly like a single provider."""

    name = "gemini"

    def __init__(self, api_keys, model, cooldown_seconds=DEFAULT_COOLDOWN_SECONDS, timeout=30, state_store=None):
        if not api_keys:
            raise ValueError("GeminiKeyManager requires at least one API key.")
        self.model = model
        self.cooldown_seconds = cooldown_seconds
        self._key_order = list(api_keys)  # fixed order — round robin, not random
        self._providers = {key: GeminiProvider(api_key=key, model=model, timeout=timeout) for key in api_keys}
        self._state_store = state_store or InMemoryKeyStateStore(api_keys)

    def stats(self):
        """For the admin panel (Phase 13) — never exposes the raw key."""
        return self._state_store.get_stats(self._key_order)

    # --- Provider-shaped interface --------------------------------------------
    def _with_key_rotation(self, method_name, *args, **kwargs):
        attempts = 0
        max_attempts = len(self._key_order)
        last_error = None

        while attempts < max_attempts:
            key = self._state_store.pick_next_key(self._key_order)
            if key is None:
                break  # all keys in cooldown

            provider = self._providers[key]
            method = getattr(provider, method_name)
            try:
                result = method(*args, **kwargs)
                self._state_store.record_success(key)
                return result
            except ProviderRateLimitError as exc:
                self._state_store.record_rate_limit(key, self.cooldown_seconds)
                last_error = exc
            except ProviderTransientError as exc:
                self._state_store.record_failure(key, cooldown=False, cooldown_seconds=self.cooldown_seconds)
                last_error = exc
            except ProviderAuthError as exc:
                # This specific key is misconfigured — cool it down so we
                # don't keep hammering a dead key, and try the next one.
                self._state_store.record_failure(key, cooldown=True, cooldown_seconds=self.cooldown_seconds)
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
        key = self._state_store.pick_next_key(self._key_order)
        if key is None:
            raise ProviderRateLimitError("All Gemini API keys are currently in cooldown.")
        provider = self._providers[key]
        try:
            yield from provider.stream(prompt, **kwargs)
            self._state_store.record_success(key)
        except (ProviderRateLimitError, ProviderTransientError, ProviderAuthError):
            self._state_store.record_failure(key, cooldown=True, cooldown_seconds=self.cooldown_seconds)
            raise
