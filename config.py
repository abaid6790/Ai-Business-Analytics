"""
Environment-based configuration.

Adding a new AI provider or changing infra settings should never require
touching business logic — everything provider/infra-related is read from
environment variables here and consumed via `current_app.config`.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(env_value, default=False):
    if env_value is None:
        return default
    return str(env_value).strip().lower() in ("1", "true", "yes", "on")


def _list(env_value, default=None):
    if not env_value:
        return default or []
    return [item.strip() for item in env_value.split(",") if item.strip()]


class BaseConfig:
    # --- Core ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    BASE_DIR = BASE_DIR

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Uploads ---
    MAX_CONTENT_LENGTH_MB = int(os.environ.get("MAX_CONTENT_LENGTH_MB", 50))
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH_MB * 1024 * 1024
    UPLOAD_FOLDER = str(BASE_DIR / os.environ.get("UPLOAD_FOLDER", "data/uploads"))
    PROCESSED_FOLDER = str(BASE_DIR / os.environ.get("PROCESSED_FOLDER", "data/processed"))
    MODELS_FOLDER = str(BASE_DIR / os.environ.get("MODELS_FOLDER", "data/models"))
    REPORTS_FOLDER = str(BASE_DIR / os.environ.get("REPORTS_FOLDER", "data/reports"))
    ALLOWED_UPLOAD_EXTENSIONS = {"csv", "xlsx", "xls"}

    # --- Dataset processing ---
    # Below this size, we read the whole file into memory once for exact
    # stats (duplicates, precise memory usage). Above it, we fall back to
    # chunked reads and skip duplicate detection, to stay usable on an
    # 8GB-RAM machine (see spec section 31).
    DATASET_FULL_PROFILE_MAX_BYTES = int(
        os.environ.get("DATASET_FULL_PROFILE_MAX_BYTES", 150 * 1024 * 1024)
    )
    DATASET_CHUNK_SIZE_ROWS = int(os.environ.get("DATASET_CHUNK_SIZE_ROWS", 50_000))
    DATASET_PREVIEW_ROWS = int(os.environ.get("DATASET_PREVIEW_ROWS", 15))
    DATASET_TEMP_SUBFOLDER = "tmp"
    DATASET_TEMP_MAX_AGE_HOURS = int(os.environ.get("DATASET_TEMP_MAX_AGE_HOURS", 24))

    # --- Email ---
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = _bool(os.environ.get("MAIL_USE_TLS"), True)
    MAIL_USE_SSL = _bool(os.environ.get("MAIL_USE_SSL"), False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "no-reply@ai-analytics.local")
    # If no MAIL_USERNAME is configured, the app logs emails instead of sending them.
    MAIL_SUPPRESS_SEND = not bool(MAIL_USERNAME)

    # --- Security tokens ---
    EMAIL_VERIFICATION_SALT = os.environ.get("EMAIL_VERIFICATION_SALT", "email-verification-salt")
    PASSWORD_RESET_SALT = os.environ.get("PASSWORD_RESET_SALT", "password-reset-salt")
    EMAIL_TOKEN_MAX_AGE_SECONDS = int(os.environ.get("EMAIL_TOKEN_MAX_AGE_SECONDS", 86400))
    PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS = int(
        os.environ.get("PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS", 3600)
    )

    # --- Password policy ---
    PASSWORD_MIN_LENGTH = 8

    # --- Rate limiting ---
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    AUTH_RATE_LIMIT = os.environ.get("AUTH_RATE_LIMIT", "10 per minute")
    UPLOAD_RATE_LIMIT = os.environ.get("UPLOAD_RATE_LIMIT", "20 per minute")
    AI_RATE_LIMIT = os.environ.get("AI_RATE_LIMIT", "20 per minute")
    ML_TRAIN_RATE_LIMIT = os.environ.get("ML_TRAIN_RATE_LIMIT", "5 per minute")

    # --- Session / cookies ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 14  # 14 days

    # --- AI Provider configuration ---
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini")
    AI_PROVIDER_ORDER = _list(os.environ.get("AI_PROVIDER_ORDER"), ["gemini"])

    GEMINI_API_KEYS = [
        key
        for key in [
            os.environ.get("GEMINI_API_KEY_1"),
            os.environ.get("GEMINI_API_KEY_2"),
            os.environ.get("GEMINI_API_KEY_3"),
            os.environ.get("GEMINI_API_KEY_4"),
        ]
        if key
    ]
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-70b-versatile")

    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
    OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/auto")

    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    AI_DAILY_REQUEST_LIMIT_PER_USER = int(os.environ.get("AI_DAILY_REQUEST_LIMIT_PER_USER", 100))
    AI_MONTHLY_REQUEST_LIMIT_PER_USER = int(
        os.environ.get("AI_MONTHLY_REQUEST_LIMIT_PER_USER", 2000)
    )

    # --- Admin bootstrap ---
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

    # --- Logging ---
    LOG_FOLDER = str(BASE_DIR / "logs")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = True


class TestingConfig(BaseConfig):
    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    MAIL_SUPPRESS_SEND = True
    RATELIMIT_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_ENABLED = True


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return CONFIG_MAP.get(env, DevelopmentConfig)
