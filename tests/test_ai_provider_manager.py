import pytest

from app.services.ai.base_provider import (
    BaseAIProvider,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderResponse,
    ProviderTransientError,
)
from app.services.ai.provider_manager import (
    AIProviderManager,
    AllProvidersExhaustedError,
    UsageLimitExceededError,
)


class ScriptedTestProvider(BaseAIProvider):
    """A provider whose _send() follows a scripted list of outcomes."""

    def __init__(self, name, model, outcomes):
        super().__init__(api_key="test-key", model=model)
        self.name = name
        self._outcomes = list(outcomes)
        self.call_count = 0

    def _send(self, prompt, **kwargs):
        self.call_count += 1
        if not self._outcomes:
            return {"text": "default"}
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _manager_with_providers(providers, order, usage_log=None, **config_overrides):
    """Builds an AIProviderManager bypassing config-based provider
    construction — injects pre-built fake providers directly for testing."""
    config = {
        "AI_PROVIDER_ORDER": order,
        "GEMINI_API_KEYS": [],  # prevent real provider construction
        **config_overrides,
    }
    usage_log = usage_log if usage_log is not None else []

    def logger(record):
        usage_log.append(record)

    manager = AIProviderManager(config, usage_logger=logger)
    manager.providers = providers  # inject fakes after construction
    manager._usage_log = usage_log
    return manager


def test_falls_back_to_next_provider_on_rate_limit():
    primary = ScriptedTestProvider("primary", "model-a", [ProviderRateLimitError("quota")])
    secondary = ScriptedTestProvider("secondary", "model-b", [{"text": "from secondary"}])

    manager = _manager_with_providers(
        {"primary": primary, "secondary": secondary}, ["primary", "secondary"]
    )

    result = manager.generate("hello", use_cache=False)
    assert result.text == "from secondary"
    assert result.provider == "secondary"


def test_falls_back_on_transient_error():
    primary = ScriptedTestProvider("primary", "model-a", [ProviderTransientError("network")])
    secondary = ScriptedTestProvider("secondary", "model-b", [{"text": "recovered"}])

    manager = _manager_with_providers(
        {"primary": primary, "secondary": secondary}, ["primary", "secondary"]
    )

    result = manager.generate("hello", use_cache=False)
    assert result.text == "recovered"


def test_invalid_request_error_does_not_fall_back():
    primary = ScriptedTestProvider("primary", "model-a", [ProviderInvalidRequestError("bad prompt")])
    secondary = ScriptedTestProvider("secondary", "model-b", [{"text": "should not be called"}])

    manager = _manager_with_providers(
        {"primary": primary, "secondary": secondary}, ["primary", "secondary"]
    )

    with pytest.raises(ProviderInvalidRequestError):
        manager.generate("hello", use_cache=False)

    assert secondary.call_count == 0  # never attempted


def test_all_providers_exhausted_raises():
    primary = ScriptedTestProvider("primary", "model-a", [ProviderRateLimitError("q1")])
    secondary = ScriptedTestProvider("secondary", "model-b", [ProviderRateLimitError("q2")])

    manager = _manager_with_providers(
        {"primary": primary, "secondary": secondary}, ["primary", "secondary"]
    )

    with pytest.raises(AllProvidersExhaustedError):
        manager.generate("hello", use_cache=False)


def test_fallback_order_is_configurable():
    a = ScriptedTestProvider("a", "model-a", [ProviderRateLimitError("q")])
    b = ScriptedTestProvider("b", "model-b", [{"text": "b wins"}])
    c = ScriptedTestProvider("c", "model-c", [{"text": "c should not run"}])

    manager = _manager_with_providers({"a": a, "b": b, "c": c}, ["a", "b", "c"])
    result = manager.generate("hello", use_cache=False)
    assert result.text == "b wins"
    assert c.call_count == 0


def test_cache_hit_skips_provider_call():
    primary = ScriptedTestProvider("primary", "model-a", [{"text": "computed once"}])
    manager = _manager_with_providers({"primary": primary}, ["primary"])

    first = manager.generate("same prompt", use_cache=True)
    second = manager.generate("same prompt", use_cache=True)

    assert first.text == "computed once"
    assert second.text == "computed once"
    assert second.cached is True
    assert primary.call_count == 1


def test_cache_miss_for_different_prompts():
    primary = ScriptedTestProvider(
        "primary", "model-a", [{"text": "answer one"}, {"text": "answer two"}]
    )
    manager = _manager_with_providers({"primary": primary}, ["primary"])

    r1 = manager.generate("prompt one", use_cache=True)
    r2 = manager.generate("prompt two", use_cache=True)

    assert r1.text == "answer one"
    assert r2.text == "answer two"
    assert primary.call_count == 2


def test_cache_disabled_always_calls_provider():
    primary = ScriptedTestProvider("primary", "model-a", [{"text": "a"}, {"text": "b"}])
    manager = _manager_with_providers({"primary": primary}, ["primary"])

    manager.generate("same prompt", use_cache=False)
    manager.generate("same prompt", use_cache=False)

    assert primary.call_count == 2


def test_usage_logged_on_success():
    primary = ScriptedTestProvider(
        "primary", "model-a", [{"text": "ok", "prompt_tokens": 3, "completion_tokens": 7}]
    )
    log = []
    manager = _manager_with_providers({"primary": primary}, ["primary"], usage_log=log)

    manager.generate("hello", user_id=42, use_cache=False)

    assert len(log) == 1
    assert log[0]["success"] is True
    assert log[0]["user_id"] == 42
    assert log[0]["provider"] == "primary"
    assert log[0]["prompt_tokens"] == 3


def test_usage_logged_on_failure_for_each_attempted_provider():
    primary = ScriptedTestProvider("primary", "model-a", [ProviderRateLimitError("q")])
    secondary = ScriptedTestProvider("secondary", "model-b", [{"text": "ok"}])
    log = []
    manager = _manager_with_providers(
        {"primary": primary, "secondary": secondary}, ["primary", "secondary"], usage_log=log
    )

    manager.generate("hello", user_id=1, use_cache=False)

    assert len(log) == 2
    assert log[0]["success"] is False
    assert log[0]["provider"] == "primary"
    assert log[1]["success"] is True
    assert log[1]["provider"] == "secondary"


def test_cache_hit_logs_usage_with_cache_hit_true():
    primary = ScriptedTestProvider("primary", "model-a", [{"text": "cached me"}])
    log = []
    manager = _manager_with_providers({"primary": primary}, ["primary"], usage_log=log)

    manager.generate("x", user_id=1, use_cache=True)
    manager.generate("x", user_id=1, use_cache=True)

    assert log[0]["cache_hit"] is False
    assert log[1]["cache_hit"] is True


def test_usage_limit_exceeded_blocks_request():
    primary = ScriptedTestProvider("primary", "model-a", [{"text": "should not run"}])
    manager = _manager_with_providers(
        {"primary": primary}, ["primary"],
        AI_DAILY_REQUEST_LIMIT_PER_USER=5,
    )
    manager.config["usage_checker"] = lambda user_id: (5, 5)

    with pytest.raises(UsageLimitExceededError):
        manager.generate("hello", user_id=1, use_cache=False)

    assert primary.call_count == 0


def test_usage_limit_not_checked_without_user_id():
    primary = ScriptedTestProvider("primary", "model-a", [{"text": "ok"}])
    manager = _manager_with_providers(
        {"primary": primary}, ["primary"],
        AI_DAILY_REQUEST_LIMIT_PER_USER=5,
    )
    manager.config["usage_checker"] = lambda user_id: (999, 999)

    result = manager.generate("hello", user_id=None, use_cache=False)
    assert result.text == "ok"


def test_generate_json_goes_through_manager():
    primary = ScriptedTestProvider("primary", "model-a", [{"text": '{"total": 5}'}])
    manager = _manager_with_providers({"primary": primary}, ["primary"])

    result = manager.generate_json("give me json", use_cache=False)
    assert result.parsed == {"total": 5}


def test_analyze_goes_through_manager():
    primary = ScriptedTestProvider("primary", "model-a", [{"text": "insight text"}])
    manager = _manager_with_providers({"primary": primary}, ["primary"])

    result = manager.analyze({"total": 100}, "what is the total?", use_cache=False)
    assert result.text == "insight text"


def test_stream_yields_chunks_and_logs_usage():
    class StreamingProvider(BaseAIProvider):
        name = "streamer"

        def _send(self, prompt, **kwargs):
            return {"text": "unused"}

        def stream(self, prompt, **kwargs):
            yield "chunk1"
            yield "chunk2"

    provider = StreamingProvider(api_key="k", model="m")
    log = []
    manager = _manager_with_providers({"streamer": provider}, ["streamer"], usage_log=log)

    chunks = list(manager.stream("hello", user_id=1))
    assert chunks == ["chunk1", "chunk2"]
    assert log[0]["success"] is True


def test_stream_falls_back_if_first_provider_fails_before_yielding():
    class FailingProvider(BaseAIProvider):
        name = "failing"

        def _send(self, prompt, **kwargs):
            return {"text": "unused"}

        def stream(self, prompt, **kwargs):
            raise ProviderRateLimitError("quota")
            yield  # pragma: no cover

    class WorkingProvider(BaseAIProvider):
        name = "working"

        def _send(self, prompt, **kwargs):
            return {"text": "unused"}

        def stream(self, prompt, **kwargs):
            yield "worked"

    manager = _manager_with_providers(
        {"failing": FailingProvider(api_key="k", model="m"), "working": WorkingProvider(api_key="k", model="m")},
        ["failing", "working"],
    )

    chunks = list(manager.stream("hello"))
    assert chunks == ["worked"]


def test_no_providers_configured_raises_exhausted():
    manager = _manager_with_providers({}, [])
    with pytest.raises(AllProvidersExhaustedError):
        manager.generate("hello", use_cache=False)
