import requests

from app.services.ai.base_provider import BaseAIProvider, ProviderInvalidRequestError, ProviderTransientError
from app.services.ai.http_utils import raise_for_status

BASE_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 1024


class ClaudeProvider(BaseAIProvider):
    name = "claude"

    def _send(self, prompt: str, **kwargs) -> dict:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", DEFAULT_MAX_TOKENS),
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            resp = requests.post(BASE_URL, json=payload, headers=headers, timeout=self.timeout)
        except requests.Timeout as exc:
            raise ProviderTransientError(f"Claude request timed out: {exc}") from exc
        except requests.RequestException as exc:
            raise ProviderTransientError(f"Claude request failed: {exc}") from exc

        raise_for_status(resp, "Claude")

        data = resp.json()
        try:
            text = "".join(
                block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise ProviderInvalidRequestError(f"Claude returned an unexpected response shape: {exc}") from exc

        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens")
        completion_tokens = usage.get("output_tokens")
        total_tokens = (
            (prompt_tokens or 0) + (completion_tokens or 0)
            if prompt_tokens is not None or completion_tokens is not None
            else None
        )

        return {
            "text": text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "raw": data,
        }
