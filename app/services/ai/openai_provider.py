import requests

from app.services.ai.base_provider import BaseAIProvider, ProviderInvalidRequestError, ProviderTransientError
from app.services.ai.http_utils import raise_for_status

BASE_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(BaseAIProvider):
    name = "openai"

    def _send(self, prompt: str, **kwargs) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            resp = requests.post(BASE_URL, json=payload, headers=headers, timeout=self.timeout)
        except requests.Timeout as exc:
            raise ProviderTransientError(f"OpenAI request timed out: {exc}") from exc
        except requests.RequestException as exc:
            raise ProviderTransientError(f"OpenAI request failed: {exc}") from exc

        raise_for_status(resp, "OpenAI")

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise ProviderInvalidRequestError(f"OpenAI returned an unexpected response shape: {exc}") from exc

        usage = data.get("usage", {})
        return {
            "text": text,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "raw": data,
        }
