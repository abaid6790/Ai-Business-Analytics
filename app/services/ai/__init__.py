"""
Lazily builds one AIProviderManager per Flask app and caches it on
`app.extensions`, so the (potentially expensive-to-construct, key-holding)
manager is built once rather than per-request. This is the only function
routes/services should call to get a manager — never construct
AIProviderManager directly outside of tests.
"""

from datetime import datetime, timezone

from app.services.ai.provider_manager import AIProviderManager

_EXTENSION_KEY = "ai_provider_manager"


def get_provider_manager(app):
    if _EXTENSION_KEY in app.extensions:
        return app.extensions[_EXTENSION_KEY]

    config = _build_manager_config(app)
    manager = AIProviderManager(config)
    app.extensions[_EXTENSION_KEY] = manager
    return manager


def _build_manager_config(app) -> dict:
    keys = (
        "AI_PROVIDER_ORDER", "GEMINI_API_KEYS", "GEMINI_MODEL",
        "GROQ_API_KEY", "GROQ_MODEL",
        "OPENROUTER_API_KEY", "OPENROUTER_MODEL",
        "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL",
        "OPENAI_API_KEY", "OPENAI_MODEL",
        "AI_DAILY_REQUEST_LIMIT_PER_USER", "AI_MONTHLY_REQUEST_LIMIT_PER_USER",
        "REDIS_URL",
    )
    config = {key: app.config.get(key) for key in keys}
    config["usage_checker"] = _make_usage_checker()

    with app.app_context():
        _apply_setting_overrides(config)

    return config


def _apply_setting_overrides(config: dict) -> None:
    """Reads admin-configured overrides from the database, if any have
    been set. Falls back silently to the .env-derived defaults already in
    `config` when the settings table doesn't exist yet (e.g. before the
    first migration runs) or no override has been saved."""
    try:
        from app.services.system_settings import get_setting

        daily_override = get_setting("AI_DAILY_REQUEST_LIMIT_PER_USER")
        if daily_override is not None:
            config["AI_DAILY_REQUEST_LIMIT_PER_USER"] = int(daily_override)

        monthly_override = get_setting("AI_MONTHLY_REQUEST_LIMIT_PER_USER")
        if monthly_override is not None:
            config["AI_MONTHLY_REQUEST_LIMIT_PER_USER"] = int(monthly_override)

        order_override = get_setting("AI_PROVIDER_ORDER")
        if order_override:
            config["AI_PROVIDER_ORDER"] = [p.strip() for p in order_override.split(",") if p.strip()]
    except Exception:
        pass  # DB not ready / no app context — use static config as-is


def _make_usage_checker():
    def checker(user_id):
        from app.models import AIUsage

        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        daily_count = AIUsage.query.filter(
            AIUsage.user_id == user_id,
            AIUsage.cache_hit.is_(False),
            AIUsage.created_at >= day_start,
        ).count()
        monthly_count = AIUsage.query.filter(
            AIUsage.user_id == user_id,
            AIUsage.cache_hit.is_(False),
            AIUsage.created_at >= month_start,
        ).count()
        return daily_count, monthly_count

    return checker
