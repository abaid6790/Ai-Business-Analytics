import time

import pytest

redis = pytest.importorskip("redis")

from app.services.ai.base_provider import ProviderRateLimitError, ProviderResponse
from app.services.ai.cache import RedisResponseCache
from app.services.ai.gemini_key_manager import GeminiKeyManager
from app.services.ai.key_state_store import InMemoryKeyStateStore, RedisKeyStateStore
from app.services.ai.provider_manager import AIProviderManager


def _redis_client_or_skip(db=0):
    try:
        client = redis.from_url(f"redis://localhost:6379/{db}", socket_connect_timeout=1)
        client.ping()
        client.flushdb()
        return client
    except Exception:
        pytest.skip("Redis is not available in this environment")


class ScriptedProvider:
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

    def stream(self, prompt, **kwargs):
        yield self._next_outcome().text


def test_redis_cache_set_and_get_roundtrip():
    client = _redis_client_or_skip(db=10)
    cache = RedisResponseCache(client)
    response = ProviderResponse(text="cached answer", provider="gemini", model="m", prompt_tokens=5)
    cache.set("key1", response)
    retrieved = cache.get("key1")
    assert retrieved.text == "cached answer"
    assert retrieved.prompt_tokens == 5


def test_redis_cache_returns_none_for_missing_key():
    client = _redis_client_or_skip(db=10)
    cache = RedisResponseCache(client)
    assert cache.get("nonexistent") is None


def test_redis_cache_respects_ttl():
    client = _redis_client_or_skip(db=10)
    cache = RedisResponseCache(client)
    cache.set("key1", ProviderResponse(text="x", provider="p", model="m"), ttl_seconds=1)
    assert cache.get("key1") is not None
    time.sleep(1.5)
    assert cache.get("key1") is None


def test_redis_cache_clear_only_affects_its_own_namespace():
    client = _redis_client_or_skip(db=10)
    cache = RedisResponseCache(client, key_prefix="test_ns:")
    client.set("unrelated_key", "should survive")
    cache.set("key1", ProviderResponse(text="x", provider="p", model="m"))
    cache.clear()
    assert cache.get("key1") is None
    assert client.get("unrelated_key") == b"should survive"


def test_redis_cache_corrupted_entry_treated_as_miss():
    client = _redis_client_or_skip(db=10)
    cache = RedisResponseCache(client, key_prefix="test_ns2:")
    client.set("test_ns2:badkey", b"not valid pickle data")
    assert cache.get("badkey") is None


def test_redis_key_state_round_robin():
    client = _redis_client_or_skip(db=11)
    store = RedisKeyStateStore(client, pool_namespace="rr_test")
    keys = ["k1", "k2", "k3"]
    picks = [store.pick_next_key(keys) for _ in range(6)]
    assert sorted(picks) == sorted(keys * 2)


def test_redis_key_state_skips_cooldown_key():
    client = _redis_client_or_skip(db=11)
    store = RedisKeyStateStore(client, pool_namespace="cooldown_test")
    keys = ["k1", "k2"]
    store.record_rate_limit("k1", cooldown_seconds=60)
    picks = [store.pick_next_key(keys) for _ in range(4)]
    assert "k1" not in picks
    assert all(p == "k2" for p in picks)


def test_redis_key_state_cooldown_expires():
    client = _redis_client_or_skip(db=11)
    store = RedisKeyStateStore(client, pool_namespace="expiry_test")
    keys = ["k1", "k2"]
    store.record_rate_limit("k1", cooldown_seconds=1)
    time.sleep(1.2)
    picks = [store.pick_next_key(keys) for _ in range(4)]
    assert "k1" in picks


def test_redis_key_state_stats_never_exposes_raw_key():
    client = _redis_client_or_skip(db=11)
    store = RedisKeyStateStore(client, pool_namespace="secret_test")
    secret_key = "AIzaSySUPER-SECRET-VALUE-DO-NOT-LEAK"
    store.record_success(secret_key)
    stats = store.get_stats([secret_key])
    assert secret_key not in str(stats)
    assert stats[0]["key_suffix"] == secret_key[-4:]


def test_redis_key_state_tracks_counts_correctly():
    client = _redis_client_or_skip(db=11)
    store = RedisKeyStateStore(client, pool_namespace="counts_test")
    store.record_success("k1")
    store.record_success("k1")
    store.record_failure("k1", cooldown=False, cooldown_seconds=60)
    store.record_rate_limit("k1", cooldown_seconds=60)
    stats = store.get_stats(["k1"])[0]
    assert stats["requests"] == 4
    assert stats["failures"] == 1
    assert stats["rate_limit_events"] == 1


def test_gemini_key_manager_with_redis_backend_full_rotation():
    client = _redis_client_or_skip(db=12)
    store = RedisKeyStateStore(client, pool_namespace="gemini_full_test")
    # Pre-seed keyA into cooldown deterministically, rather than relying on
    # scripted failures racing against Redis's round-robin pick order.
    store.record_rate_limit("keyA", cooldown_seconds=60)

    manager = GeminiKeyManager(api_keys=["keyA", "keyB"], model="gemini-1.5-flash", state_store=store)
    manager._providers["keyA"] = ScriptedProvider("m", [ProviderResponse(text="should not be used", provider="gemini", model="m")])
    manager._providers["keyB"] = ScriptedProvider("m", [ProviderResponse(text="from B", provider="gemini", model="m")])

    result = manager.generate("prompt")
    assert result.text == "from B"  # keyA skipped entirely — already in cooldown
    assert manager._providers["keyA"].call_count == 0

    stats = manager.stats()
    key_a_stats = next(s for s in stats if s["key_suffix"] == "keyA"[-4:])
    assert key_a_stats["in_cooldown"] is True


def test_gemini_key_manager_redis_state_persists_across_manager_instances():
    """The whole point of Redis-backed state: a NEW GeminiKeyManager
    instance (simulating a different worker process) sees the same
    cooldown state a previous instance wrote."""
    client = _redis_client_or_skip(db=13)
    namespace = "persist_test"
    store1 = RedisKeyStateStore(client, pool_namespace=namespace)
    store1.record_rate_limit("keyA", cooldown_seconds=60)  # manager1 "writes" this cooldown

    store2 = RedisKeyStateStore(client, pool_namespace=namespace)
    manager2 = GeminiKeyManager(api_keys=["keyA", "keyB"], model="m", state_store=store2)
    stats_from_manager2 = manager2.stats()
    key_a_stats = next(s for s in stats_from_manager2 if s["key_suffix"] == "keyA"[-4:])
    assert key_a_stats["in_cooldown"] is True  # manager2 sees what was written via store1


def test_all_keys_exhausted_with_redis_backend_raises():
    client = _redis_client_or_skip(db=14)
    store = RedisKeyStateStore(client, pool_namespace="exhausted_test")
    manager = GeminiKeyManager(api_keys=["keyA", "keyB"], model="m", state_store=store)
    manager._providers["keyA"] = ScriptedProvider("m", [ProviderRateLimitError("quota A")])
    manager._providers["keyB"] = ScriptedProvider("m", [ProviderRateLimitError("quota B")])
    with pytest.raises(ProviderRateLimitError):
        manager.generate("prompt")


def test_ai_provider_manager_selects_redis_cache_when_configured():
    _redis_client_or_skip(db=15)
    manager = AIProviderManager({
        "AI_PROVIDER_ORDER": ["gemini"], "GEMINI_API_KEYS": ["k1"],
        "REDIS_URL": "redis://localhost:6379/15",
    })
    assert isinstance(manager.cache, RedisResponseCache)


def test_ai_provider_manager_selects_redis_key_state_when_configured():
    _redis_client_or_skip(db=15)
    manager = AIProviderManager({
        "AI_PROVIDER_ORDER": ["gemini"], "GEMINI_API_KEYS": ["k1"],
        "REDIS_URL": "redis://localhost:6379/15",
    })
    assert isinstance(manager.providers["gemini"]._state_store, RedisKeyStateStore)


def test_ai_provider_manager_falls_back_without_redis_url():
    manager = AIProviderManager({"AI_PROVIDER_ORDER": ["gemini"], "GEMINI_API_KEYS": ["k1"]})
    from app.services.ai.cache import InMemoryResponseCache
    assert isinstance(manager.cache, InMemoryResponseCache)
    assert isinstance(manager.providers["gemini"]._state_store, InMemoryKeyStateStore)


def test_ai_provider_manager_falls_back_gracefully_on_unreachable_redis():
    manager = AIProviderManager({
        "AI_PROVIDER_ORDER": ["gemini"], "GEMINI_API_KEYS": ["k1"],
        "REDIS_URL": "redis://this-host-does-not-exist-at-all:6379/0",
    })
    from app.services.ai.cache import InMemoryResponseCache
    assert isinstance(manager.cache, InMemoryResponseCache)


def test_ai_provider_manager_end_to_end_caching_via_redis():
    _redis_client_or_skip(db=9)
    log = []
    manager = AIProviderManager(
        {"AI_PROVIDER_ORDER": ["fake"], "GEMINI_API_KEYS": [], "REDIS_URL": "redis://localhost:6379/9"},
        usage_logger=lambda record: log.append(record),
    )
    from app.services.ai.base_provider import BaseAIProvider

    class FakeProvider(BaseAIProvider):
        name = "fake"
        call_count = 0

        def _send(self, prompt, **kwargs):
            FakeProvider.call_count += 1
            return {"text": "computed once"}

    manager.providers = {"fake": FakeProvider(api_key="k", model="m")}
    first = manager.generate("same prompt", use_cache=True)
    second = manager.generate("same prompt", use_cache=True)
    assert first.text == "computed once"
    assert second.cached is True
    assert FakeProvider.call_count == 1
