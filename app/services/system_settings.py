"""
Thin get/set wrapper around SystemSetting — lets admin-configured values
(usage limits, AI provider fallback order) override the static .env
defaults without a restart, while still falling back to app.config when
no override has been set.
"""

from app.extensions import db
from app.models import SystemSetting


def get_setting(key: str, default=None):
    setting = db.session.get(SystemSetting, key)
    if setting is None or setting.value is None:
        return default
    return setting.value


def set_setting(key: str, value: str) -> None:
    setting = db.session.get(SystemSetting, key)
    if setting is None:
        setting = SystemSetting(key=key, value=value)
        db.session.add(setting)
    else:
        setting.value = value
    db.session.commit()
