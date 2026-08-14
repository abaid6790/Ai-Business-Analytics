import requests

from app.services.ai.base_provider import (
    ProviderAuthError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTransientError,
)


def raise_for_status(resp: requests.Response, provider_label: str) -> None:
    if resp.ok:
        return
    try:
        body = resp.json()
        message = body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else body.get("error")
        message = message or resp.text
    except ValueError:
        message = resp.text

    if resp.status_code == 429:
        raise ProviderRateLimitError(f"{provider_label} rate limit: {message}")
    if resp.status_code in (401, 403):
        raise ProviderAuthError(f"{provider_label} auth error: {message}")
    if resp.status_code >= 500:
        raise ProviderTransientError(f"{provider_label} server error ({resp.status_code}): {message}")
    raise ProviderInvalidRequestError(f"{provider_label} request error ({resp.status_code}): {message}")
