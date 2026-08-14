from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_token(email: str, salt_config_key: str) -> str:
    salt = current_app.config[salt_config_key]
    return _serializer().dumps(email, salt=salt)


def verify_token(token: str, salt_config_key: str, max_age_config_key: str):
    """Returns the email encoded in the token, or None if invalid/expired."""
    salt = current_app.config[salt_config_key]
    max_age = current_app.config[max_age_config_key]
    try:
        return _serializer().loads(token, salt=salt, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
