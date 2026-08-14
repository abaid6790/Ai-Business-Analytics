"""
AIProviderManager is the ONLY thing the rest of the application is allowed
to call for AI requests (spec section 18). It ties together:

  - Provider fallback (spec 21): tries providers in AI_PROVIDER_ORDER;
    Gemini's own multi-key rotation (spec 19) happens *inside* the Gemini
    pool before this manager ever sees a failure from "gemini" as a whole.
  - Response caching (spec 22): identical (provider, model, prompt,
    context) requests return a cached response instead of hitting the API.
  - Usage tracking (spec 23): every attempt is logged to AIUsage.
  - Daily/monthly limits (spec 23): checked before any provider is called.

NOTE on process boundaries: cache and Gemini key-rotation state both live
in-process (see cache.py / gemini_key_manager.py). Under gunicorn with
multiple workers, each worker has its own view of key cooldowns and cache
contents. That's an acceptable MVP trade-off — behavior is still correct
(worst case: a cooling-down key gets retried once by a different worker),
just not perfectly coordinated. Moving state to Redis is a scoped follow-up
that doesn't change any of the logic here.
"""

import time

from app.services.ai.base_provider import (
    ProviderAuthError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTransientError,
)
from app.services.ai.cache import InMemoryResponseCache, build_cache_key
from app.services.ai.gemini_key_manager import GeminiKeyManager
from app.services.ai.groq_provider import GroqProvider
from app.services.ai.openrouter_provider import OpenRouterProvider
from app.services.ai.claude_provider import ClaudeProvider
from app.services.ai.openai_provider import OpenAIProvider


class AllProvidersExhaustedError(Exception):
    """Every configured provider in the fallback order failed."""


class UsageLimitExceededError(Exception):
    """The user has hit their daily or monthly AI request limit."""


class AIProviderManager:
    def __init__(self, config, usage_logger=None, cache=None):
        """
        `config` is a plain dict of the relevant app.config values (not the
        Flask app itself) so this class can be constructed and tested
        without a Flask app context.

        `usage_logger` is an injectable callable(record: dict) -> None,
        defaulting to writing AIUsage rows via SQLAlchemy. Tests can pass a
        list-appending stub instead of touching the database.
        """
        self.config = config
        self.provider_order = config.get("AI_PROVIDER_ORDER") or ["gemini"]
        self.cache = cache if cache is not None else InMemoryResponseCache()
        self.usage_logger = usage_logger or _default_usage_logger
        self.providers = self._build_providers(config)

    # ------------------------------------------------------------------
    # Provider construction
    # ------------------------------------------------------------------
    @staticmethod
    def _build_providers(config):
        """Only providers with an API key actually configured are included
        — an entry present in AI_PROVIDER_ORDER but missing its key is
        silently skipped rather than erroring at startup, so partial
        configuration (e.g. only Gemini set up) still works."""
        providers = {}

        gemini_keys = config.get("GEMINI_API_KEYS") or []
        if gemini_keys:
            providers["gemini"] = GeminiKeyManager(
                api_keys=gemini_keys, model=config.get("GEMINI_MODEL", "gemini-1.5-flash")
            )

        if config.get("GROQ_API_KEY"):
            providers["groq"] = GroqProvider(
                api_key=config["GROQ_API_KEY"], model=config.get("GROQ_MODEL", "llama-3.1-70b-versatile")
            )

        if config.get("OPENROUTER_API_KEY"):
            providers["openrouter"] = OpenRouterProvider(
                api_key=config["OPENROUTER_API_KEY"], model=config.get("OPENROUTER_MODEL", "openrouter/auto")
            )

        if config.get("ANTHROPIC_API_KEY"):
            providers["claude"] = ClaudeProvider(
                api_key=config["ANTHROPIC_API_KEY"], model=config.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
            )

        if config.get("OPENAI_API_KEY"):
            providers["openai"] = OpenAIProvider(
                api_key=config["OPENAI_API_KEY"], model=config.get("OPENAI_MODEL", "gpt-4o-mini")
            )

        return providers

    def configured_provider_order(self):
        """The fallback order, filtered to providers that are actually
        configured — useful for diagnostics / admin panel."""
        return [name for name in self.provider_order if name in self.providers]

    # ------------------------------------------------------------------
    # Admin-panel live updates (Phase 13)
    # ------------------------------------------------------------------
    def update_limits(self, daily=None, monthly=None):
        """Mutates self.config in place so the next usage check picks up
        the new value immediately — no restart needed. Persisting the
        change so it survives a restart is the caller's job (see
        app.services.system_settings)."""
        if daily is not None:
            self.config["AI_DAILY_REQUEST_LIMIT_PER_USER"] = daily
        if monthly is not None:
            self.config["AI_MONTHLY_REQUEST_LIMIT_PER_USER"] = monthly

    def update_provider_order(self, new_order):
        """Reorders (or narrows) the fallback chain among already-configured
        providers. Does not add a provider that has no API key configured —
        configured_provider_order() already filters against self.providers,
        so an unknown name here is simply never used, not an error."""
        self.provider_order = list(new_order)

    # ------------------------------------------------------------------
    # Public API — the four methods spec section 18 asks for
    # ------------------------------------------------------------------
    def generate(self, prompt, user_id=None, use_cache=True, context=None, **kwargs):
        return self._execute("generate", user_id, use_cache, context, prompt, **kwargs)

    def generate_json(self, prompt, user_id=None, use_cache=True, context=None, **kwargs):
        return self._execute("generate_json", user_id, use_cache, context, prompt, **kwargs)

    def analyze(self, context, question, user_id=None, use_cache=True, **kwargs):
        return self._execute("analyze", user_id, use_cache, context, context, question, **kwargs)

    def stream(self, prompt, user_id=None, **kwargs):
        """
        Streaming bypasses the cache (a cached response should be returned
        whole, not re-streamed token by token). Fallback is limited: if the
        first provider fails before yielding anything, we try the next;
        once tokens have started streaming to the caller, a mid-stream
        failure surfaces directly rather than silently restarting output
        the caller may have already displayed.
        """
        self._check_usage_limit(user_id)

        last_error = None
        for provider_name in self.configured_provider_order():
            provider = self.providers[provider_name]
            started = False
            start = time.monotonic()
            try:
                for chunk in provider.stream(prompt, **kwargs):
                    started = True
                    yield chunk
                self._log_usage(
                    user_id, provider_name, getattr(provider, "model", "unknown"),
                    "stream", True, None, time.monotonic() - start, cache_hit=False,
                )
                return
            except (ProviderRateLimitError, ProviderTransientError, ProviderAuthError) as exc:
                self._log_usage(
                    user_id, provider_name, getattr(provider, "model", "unknown"),
                    "stream", False, str(exc), time.monotonic() - start, cache_hit=False,
                )
                last_error = exc
                if started:
                    raise  # already streamed partial output — don't silently switch providers
                continue
            except ProviderInvalidRequestError as exc:
                self._log_usage(
                    user_id, provider_name, getattr(provider, "model", "unknown"),
                    "stream", False, str(exc), time.monotonic() - start, cache_hit=False,
                )
                raise

        raise AllProvidersExhaustedError(str(last_error) if last_error else "No AI providers are configured.")

    # ------------------------------------------------------------------
    # Core execution: cache -> fallback loop -> usage logging
    # ------------------------------------------------------------------
    def _execute(self, method_name, user_id, use_cache, context, *args, **kwargs):
        self._check_usage_limit(user_id)

        prompt_for_cache = args[0] if method_name != "analyze" else f"{args[1]}"
        cache_key = None

        if use_cache and self.configured_provider_order():
            primary_provider = self.configured_provider_order()[0]
            primary_model = getattr(self.providers[primary_provider], "model", "unknown")
            cache_key = build_cache_key(primary_provider, primary_model, prompt_for_cache, context)

            cached = self.cache.get(cache_key)
            if cached is not None:
                self._log_usage(
                    user_id, primary_provider, primary_model, method_name,
                    True, None, 0.0, cache_hit=True,
                )
                cached.cached = True
                return cached

        last_error = None
        for provider_name in self.configured_provider_order():
            provider = self.providers[provider_name]
            method = getattr(provider, method_name)
            start = time.monotonic()
            try:
                response = method(*args, **kwargs)
            except ProviderInvalidRequestError as exc:
                # Permanent/user error — do NOT fall back to another
                # provider (spec section 21).
                self._log_usage(
                    user_id, provider_name, getattr(provider, "model", "unknown"),
                    method_name, False, str(exc), time.monotonic() - start, cache_hit=False,
                )
                raise
            except (ProviderRateLimitError, ProviderTransientError, ProviderAuthError) as exc:
                self._log_usage(
                    user_id, provider_name, getattr(provider, "model", "unknown"),
                    method_name, False, str(exc), time.monotonic() - start, cache_hit=False,
                )
                last_error = exc
                continue

            elapsed = time.monotonic() - start
            self._log_usage(
                user_id, provider_name, getattr(provider, "model", "unknown"),
                method_name, True, None, elapsed,
                cache_hit=False,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
            )

            if use_cache and cache_key is not None and provider_name == self.configured_provider_order()[0]:
                self.cache.set(cache_key, response)

            return response

        raise AllProvidersExhaustedError(
            str(last_error) if last_error else "No AI providers are configured."
        )

    # ------------------------------------------------------------------
    # Usage limits / logging
    # ------------------------------------------------------------------
    def _check_usage_limit(self, user_id):
        if user_id is None:
            return
        daily_limit = self.config.get("AI_DAILY_REQUEST_LIMIT_PER_USER")
        monthly_limit = self.config.get("AI_MONTHLY_REQUEST_LIMIT_PER_USER")
        if not daily_limit and not monthly_limit:
            return

        checker = self.config.get("usage_checker")
        if checker is None:
            return  # no checker wired up (e.g. running outside Flask/DB context)

        daily_count, monthly_count = checker(user_id)
        if daily_limit and daily_count >= daily_limit:
            raise UsageLimitExceededError(f"Daily AI request limit reached ({daily_limit}).")
        if monthly_limit and monthly_count >= monthly_limit:
            raise UsageLimitExceededError(f"Monthly AI request limit reached ({monthly_limit}).")

    def _log_usage(self, user_id, provider, model, request_type, success, error_message,
                    elapsed_seconds, cache_hit=False, prompt_tokens=None,
                    completion_tokens=None, total_tokens=None):
        self.usage_logger({
            "user_id": user_id,
            "provider": provider,
            "model": model,
            "request_type": request_type,
            "success": success,
            "error_message": error_message,
            "response_time_ms": int(elapsed_seconds * 1000),
            "cache_hit": cache_hit,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        })


def _default_usage_logger(record):
    """Writes an AIUsage row. Imported lazily to avoid a hard dependency on
    a Flask/DB context for callers that inject their own logger (tests)."""
    from app.extensions import db
    from app.models import AIUsage

    if record["user_id"] is None:
        return  # system/anonymous calls aren't attributed to a user

    usage = AIUsage(
        user_id=record["user_id"],
        provider=record["provider"],
        model=record["model"],
        request_type=record["request_type"],
        success=record["success"],
        error_message=record["error_message"],
        prompt_tokens=record["prompt_tokens"],
        completion_tokens=record["completion_tokens"],
        total_tokens=record["total_tokens"],
        response_time_ms=record["response_time_ms"],
        cache_hit=record["cache_hit"],
    )
    db.session.add(usage)
    db.session.commit()
