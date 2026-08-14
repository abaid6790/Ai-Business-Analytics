"""
Gemini provider — calls the generativelanguage.googleapis.com REST API
directly (no SDK dependency, keeps the footprint small and the HTTP
behavior fully under our control for error-mapping).
"""

import json

import requests

from app.services.ai.base_provider import (
    BaseAIProvider,
    ProviderAuthError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTransientError,
)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(BaseAIProvider):
    name = "gemini"

    def _send(self, prompt: str, **kwargs) -> dict:
        url = f"{BASE_URL}/{self.model}:generateContent?key={self.api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
        except requests.Timeout as exc:
            raise ProviderTransientError(f"Gemini request timed out: {exc}") from exc
        except requests.RequestException as exc:
            raise ProviderTransientError(f"Gemini request failed: {exc}") from exc

        self._raise_for_status(resp)

        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise ProviderInvalidRequestError(
                f"Gemini returned an unexpected response shape: {exc}"
            ) from exc

        usage = data.get("usageMetadata", {})
        return {
            "text": text,
            "prompt_tokens": usage.get("promptTokenCount"),
            "completion_tokens": usage.get("candidatesTokenCount"),
            "total_tokens": usage.get("totalTokenCount"),
            "raw": data,
        }

    def stream(self, prompt: str, **kwargs):
        url = f"{BASE_URL}/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout, stream=True)
        except requests.Timeout as exc:
            raise ProviderTransientError(f"Gemini stream timed out: {exc}") from exc
        except requests.RequestException as exc:
            raise ProviderTransientError(f"Gemini stream failed: {exc}") from exc

        self._raise_for_status(resp)

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            chunk = line[len("data:"):].strip()
            if chunk == "[DONE]":
                break
            try:
                data = json.loads(chunk)
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                yield text
            except (ValueError, KeyError, IndexError):
                continue

    def _raise_for_status(self, resp: requests.Response) -> None:
        if resp.ok:
            return

        try:
            message = resp.json().get("error", {}).get("message", resp.text)
        except ValueError:
            message = resp.text

        if resp.status_code == 429:
            raise ProviderRateLimitError(f"Gemini rate limit: {message}")
        if resp.status_code in (401, 403):
            raise ProviderAuthError(f"Gemini auth error: {message}")
        if resp.status_code >= 500:
            raise ProviderTransientError(f"Gemini server error ({resp.status_code}): {message}")
        raise ProviderInvalidRequestError(f"Gemini request error ({resp.status_code}): {message}")
