import time

from app.services.ai.cache import InMemoryResponseCache, build_cache_key
from app.services.ai import get_provider_manager


def test_build_cache_key_deterministic():
    k1 = build_cache_key("gemini", "gemini-1.5-flash", "hello", {"a": 1})
    k2 = build_cache_key("gemini", "gemini-1.5-flash", "hello", {"a": 1})
    assert k1 == k2


def test_build_cache_key_differs_on_prompt():
    k1 = build_cache_key("gemini", "m", "prompt one", {})
    k2 = build_cache_key("gemini", "m", "prompt two", {})
    assert k1 != k2


def test_build_cache_key_differs_on_provider():
    k1 = build_cache_key("gemini", "m", "same", {})
    k2 = build_cache_key("groq", "m", "same", {})
    assert k1 != k2


def test_build_cache_key_differs_on_context():
    k1 = build_cache_key("gemini", "m", "same", {"dataset_id": 1})
    k2 = build_cache_key("gemini", "m", "same", {"dataset_id": 2})
    assert k1 != k2


def test_cache_get_set_roundtrip():
    cache = InMemoryResponseCache()
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"


def test_cache_returns_none_for_missing_key():
    cache = InMemoryResponseCache()
    assert cache.get("nonexistent") is None


def test_cache_expires_after_ttl():
    cache = InMemoryResponseCache(default_ttl_seconds=0)
    cache.set("key1", "value1", ttl_seconds=0)
    time.sleep(0.01)
    assert cache.get("key1") is None


def test_cache_clear():
    cache = InMemoryResponseCache()
    cache.set("key1", "value1")
    cache.clear()
    assert cache.get("key1") is None


def test_get_provider_manager_returns_same_instance_per_app(app):
    manager1 = get_provider_manager(app)
    manager2 = get_provider_manager(app)
    assert manager1 is manager2


def test_get_provider_manager_builds_no_providers_without_keys(app):
    manager = get_provider_manager(app)
    assert manager.providers == {}


def test_get_provider_manager_respects_provider_order(app):
    manager = get_provider_manager(app)
    assert manager.provider_order == app.config["AI_PROVIDER_ORDER"]
