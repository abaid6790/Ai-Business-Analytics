"""
Common interface every AI provider implements: generate(), generate_json(),
stream(), analyze(). Nothing outside app/services/ai/ should ever import a
specific provider (GeminiProvider, GroqProvider, ...) directly — everything
goes through AIProviderManager, which is what makes it possible to add a
new provider later without touching any Flask route.

Subclasses only need to implement `_send()` — the one truly
provider-specific piece (how to call that vendor's HTTP API and extract
text + token usage). generate/generate_json/analyze/stream are implemented
once here and shared by every provider.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Optional


# ---------------------------------------------------------------------------
# Typed errors — the provider manager reacts differently to each of these.
# ---------------------------------------------------------------------------
class ProviderError(Exception):
    """Base class for all provider-related errors."""


class ProviderRateLimitError(ProviderError):
    """Quota/rate-limit hit. Eligible for key rotation / provider fallback."""


class ProviderAuthError(ProviderError):
    """Invalid/expired API key. Eligible for provider fallback (not retry)."""


class ProviderTransientError(ProviderError):
    """Network/timeout/5xx — eligible for key rotation / provider fallback."""


class ProviderInvalidRequestError(ProviderError):
    """
    Permanent, request-shaped problem (bad prompt, 4xx that isn't auth/rate
    limit). Per spec section 21, these must NOT trigger fallback — retrying
    the same broken request against a different provider wastes a call and
    won't fix a malformed request.
    """


# ---------------------------------------------------------------------------
# Response type
# ---------------------------------------------------------------------------
@dataclass
class ProviderResponse:
    text: str
    provider: str
    model: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cached: bool = False
    parsed: Optional[dict] = field(default=None)  # populated by generate_json()
    raw: Optional[dict] = None


# ---------------------------------------------------------------------------
# Base provider
# ---------------------------------------------------------------------------
class BaseAIProvider(ABC):
    name: str = "base"

    def __init__(self, api_key: str, model: str, timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @abstractmethod
    def _send(self, prompt: str, **kwargs) -> dict:
        """
        Provider-specific HTTP call. Must return a dict with at least
        {"text": str}, and may include "prompt_tokens", "completion_tokens",
        "total_tokens", "raw". Must raise one of the typed ProviderError
        subclasses on failure — never let a raw requests exception escape,
        so the manager can react appropriately (rotate key / fall back /
        stop).
        """
        raise NotImplementedError

    def generate(self, prompt: str, **kwargs) -> ProviderResponse:
        result = self._send(prompt, **kwargs)
        return ProviderResponse(
            text=result["text"],
            provider=self.name,
            model=self.model,
            prompt_tokens=result.get("prompt_tokens"),
            completion_tokens=result.get("completion_tokens"),
            total_tokens=result.get("total_tokens"),
            raw=result.get("raw"),
        )

    def generate_json(self, prompt: str, **kwargs) -> ProviderResponse:
        json_prompt = (
            f"{prompt}\n\n"
            "Respond with ONLY valid JSON. No prose, no markdown code fences, "
            "no explanation before or after the JSON object."
        )
        response = self.generate(json_prompt, **kwargs)

        cleaned = _strip_code_fences(response.text)
        try:
            response.parsed = json.loads(cleaned)
        except (ValueError, TypeError) as exc:
            raise ProviderInvalidRequestError(
                f"{self.name} did not return valid JSON: {exc}"
            ) from exc
        return response

    def analyze(self, context: dict, question: str, **kwargs) -> ProviderResponse:
        """
        Convenience wrapper for the AI Data Analyst (Phase 8): combines a
        structured, pre-computed context (real numbers from Pandas — never
        invented) with the user's question, and instructs the model to
        answer using ONLY that context.
        """
        prompt = build_analyze_prompt(context, question)
        return self.generate(prompt, **kwargs)

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """
        Default fallback: providers that don't implement real streaming
        just yield the full response once. Providers with genuine
        server-sent-event streaming (e.g. Gemini) override this.
        """
        response = self.generate(prompt, **kwargs)
        yield response.text


def build_analyze_prompt(context: dict, question: str) -> str:
    """Shared by BaseAIProvider.analyze() (blocking) and
    AIProviderManager.stream_analyze() (streaming) so the "answer using
    ONLY this data" grounding instructions never drift between the two
    paths."""
    return (
        "You are a data analyst assistant. Answer the user's question "
        "using ONLY the structured data below. Do not invent, estimate, "
        "or guess any numbers that are not present in this data — if the "
        "data doesn't contain what's needed to answer, say so.\n\n"
        f"DATA:\n{json.dumps(context, default=str)}\n\n"
        f"QUESTION: {question}"
    )


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped
