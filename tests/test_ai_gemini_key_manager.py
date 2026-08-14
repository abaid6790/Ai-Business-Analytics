import pytest

from app.services.ai.base_provider import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponse,
    ProviderTransientError,
)
from app.services.ai.gemini_key_manager import GeminiKeyManager


class ScriptedProvider:
    """Stands in for GeminiProvider — returns/raises according to a script
    of outcomes, one per call, so we can simulate a key failing N times."""

    def __init__(self, model, outcomes):
        self.model = model
        self._outcomes = list(outcomes)
        self.call_count = 0

    def _next_outcome(self):
        self.call_count += 1
        if not self._outcomes:
            return ProviderResponse(text="default ok", provider="gemini", model=self.model)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def generate(self, prompt, **kwargs):
        return self._next_outcome()

    def generate_json(self, prompt, **kwargs):
        return self._next_outcome()

    def analyze(self, context, question, **kwargs):
        return self._next_outcome()

    def stream(self, prompt, **kwargs):
        result = self._next_outcome()
        yield result.text


def _install_scripted_providers(manager, scripts):
    """scripts: {api_key: [outcome, outcome, ...]}"""
    for key, outcomes in scripts.items():
        manager._providers[key] = ScriptedProvider(manager.model, outcomes)


def test_round_robin_not_random_order():
    manager = GeminiKeyManager(api_keys=["k1", "k2", "k3"], model="gemini-1.5-flash")
    _install_scripted_providers(manager, {
        "k1": [ProviderResponse(text="a", provider="gemini", model="m")],
        "k2": [ProviderResponse(text="b", provider="gemini", model="m")],
        "k3": [ProviderResponse(text="c", provider="gemini", model="m")],
    })

    r1 = manager.generate("p")
    r2 = manager.generate("p")
    r3 = manager.generate("p")

    assert [r1.text, r2.text, r3.text] == ["a", "b", "c"]


def test_rate_limited_key_rotates_to_next_key():
    manager = GeminiKeyManager(api_keys=["k1", "k2"], model="gemini-1.5-flash")
    _install_scripted_providers(manager, {
        "k1": [ProviderRateLimitError("quota exceeded")],
        "k2": [ProviderResponse(text="from k2", provider="gemini", model="m")],
    })

    result = manager.generate("p")
    assert result.text == "from k2"


def test_key_in_cooldown_is_skipped_on_subsequent_calls():
    manager = GeminiKeyManager(api_keys=["k1", "k2"], model="gemini-1.5-flash", cooldown_seconds=60)
    _install_scripted_providers(manager, {
        "k1": [ProviderRateLimitError("quota"), ProviderResponse(text="k1 again", provider="gemini", model="m")],
        "k2": [ProviderResponse(text="k2", provider="gemini", model="m"),
               ProviderResponse(text="k2 again", provider="gemini", model="m")],
    })

    first = manager.generate("p")  # k1 rate limited -> falls to k2
    assert first.text == "k2"

    second = manager.generate("p")  # k1 still cooling down -> should use k2 again, not retry k1
    assert second.text == "k2 again"


def test_all_keys_exhausted_raises_last_error():
    manager = GeminiKeyManager(api_keys=["k1", "k2"], model="gemini-1.5-flash")
    _install_scripted_providers(manager, {
        "k1": [ProviderRateLimitError("k1 quota")],
        "k2": [ProviderRateLimitError("k2 quota")],
    })

    with pytest.raises(ProviderRateLimitError):
        manager.generate("p")


def test_transient_error_also_rotates_key():
    manager = GeminiKeyManager(api_keys=["k1", "k2"], model="gemini-1.5-flash")
    _install_scripted_providers(manager, {
        "k1": [ProviderTransientError("network blip")],
        "k2": [ProviderResponse(text="recovered", provider="gemini", model="m")],
    })

    result = manager.generate("p")
    assert result.text == "recovered"


def test_auth_error_cools_down_key_and_tries_next():
    manager = GeminiKeyManager(api_keys=["key-one", "key-two"], model="gemini-1.5-flash")
    _install_scripted_providers(manager, {
        "key-one": [ProviderAuthError("bad key")],
        "key-two": [ProviderResponse(text="ok from k2", provider="gemini", model="m")],
    })

    result = manager.generate("p")
    assert result.text == "ok from k2"

    stats = manager.stats()
    k1_stats = next(s for s in stats if s["key_suffix"] == "key-one"[-4:])
    assert k1_stats["in_cooldown"] is True


def test_stats_never_exposes_raw_key():
    manager = GeminiKeyManager(api_keys=["super-secret-key-value"], model="gemini-1.5-flash")
    stats = manager.stats()
    for entry in stats:
        assert "super-secret-key-value" not in str(entry)


def test_stream_uses_available_key():
    manager = GeminiKeyManager(api_keys=["k1"], model="gemini-1.5-flash")
    _install_scripted_providers(manager, {
        "k1": [ProviderResponse(text="streamed text", provider="gemini", model="m")],
    })

    chunks = list(manager.stream("p"))
    assert chunks == ["streamed text"]


def test_requires_at_least_one_key():
    with pytest.raises(ValueError):
        GeminiKeyManager(api_keys=[], model="gemini-1.5-flash")
