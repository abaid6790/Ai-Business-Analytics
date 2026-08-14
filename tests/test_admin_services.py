from app.services.system_settings import get_setting, set_setting
from app.services.ai.provider_manager import AIProviderManager


def test_get_setting_returns_default_when_unset(db):
    assert get_setting("NONEXISTENT_KEY", default="fallback") == "fallback"


def test_set_and_get_setting_roundtrip(db):
    set_setting("MY_KEY", "my_value")
    assert get_setting("MY_KEY") == "my_value"


def test_set_setting_updates_existing_value(db):
    set_setting("MY_KEY", "first")
    set_setting("MY_KEY", "second")
    assert get_setting("MY_KEY") == "second"


def test_update_limits_mutates_config_in_place():
    manager = AIProviderManager({"AI_PROVIDER_ORDER": [], "GEMINI_API_KEYS": []})
    manager.update_limits(daily=50, monthly=1000)
    assert manager.config["AI_DAILY_REQUEST_LIMIT_PER_USER"] == 50
    assert manager.config["AI_MONTHLY_REQUEST_LIMIT_PER_USER"] == 1000


def test_update_limits_partial_update_only_changes_given_value():
    manager = AIProviderManager({"AI_PROVIDER_ORDER": [], "GEMINI_API_KEYS": []})
    manager.update_limits(daily=50, monthly=1000)
    manager.update_limits(daily=75)
    assert manager.config["AI_DAILY_REQUEST_LIMIT_PER_USER"] == 75
    assert manager.config["AI_MONTHLY_REQUEST_LIMIT_PER_USER"] == 1000  # unchanged


def test_update_provider_order_changes_fallback_chain():
    manager = AIProviderManager({"AI_PROVIDER_ORDER": ["gemini"], "GEMINI_API_KEYS": []})
    manager.providers = {"gemini": object(), "groq": object()}
    manager.update_provider_order(["groq", "gemini"])
    assert manager.provider_order == ["groq", "gemini"]
    assert manager.configured_provider_order() == ["groq", "gemini"]


def test_update_provider_order_filters_unconfigured_providers_from_effective_order():
    manager = AIProviderManager({"AI_PROVIDER_ORDER": ["gemini"], "GEMINI_API_KEYS": []})
    manager.providers = {"gemini": object()}
    manager.update_provider_order(["groq", "gemini"])  # groq not actually configured
    assert manager.configured_provider_order() == ["gemini"]
