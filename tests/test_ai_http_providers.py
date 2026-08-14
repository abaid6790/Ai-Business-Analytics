from unittest.mock import MagicMock, patch

import pytest
import requests

from app.services.ai.base_provider import (
    ProviderAuthError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTransientError,
)
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.groq_provider import GroqProvider
from app.services.ai.openrouter_provider import OpenRouterProvider
from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.claude_provider import ClaudeProvider


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


# --- Gemini -----------------------------------------------------------------
class TestGeminiProvider:
    def test_successful_generate(self):
        provider = GeminiProvider(api_key="k", model="gemini-1.5-flash")
        mock_resp = _mock_response(200, {
            "candidates": [{"content": {"parts": [{"text": "Hello from Gemini"}]}}],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 10, "totalTokenCount": 15},
        })
        with patch("app.services.ai.gemini_provider.requests.post", return_value=mock_resp):
            result = provider.generate("hi")
        assert result.text == "Hello from Gemini"
        assert result.prompt_tokens == 5

    def test_rate_limit_maps_to_provider_rate_limit_error(self):
        provider = GeminiProvider(api_key="k", model="gemini-1.5-flash")
        mock_resp = _mock_response(429, {"error": {"message": "quota exceeded"}})
        with patch("app.services.ai.gemini_provider.requests.post", return_value=mock_resp):
            with pytest.raises(ProviderRateLimitError):
                provider.generate("hi")

    def test_auth_error_maps_correctly(self):
        provider = GeminiProvider(api_key="bad-key", model="gemini-1.5-flash")
        mock_resp = _mock_response(401, {"error": {"message": "invalid API key"}})
        with patch("app.services.ai.gemini_provider.requests.post", return_value=mock_resp):
            with pytest.raises(ProviderAuthError):
                provider.generate("hi")

    def test_server_error_maps_to_transient(self):
        provider = GeminiProvider(api_key="k", model="gemini-1.5-flash")
        mock_resp = _mock_response(503, {"error": {"message": "overloaded"}})
        with patch("app.services.ai.gemini_provider.requests.post", return_value=mock_resp):
            with pytest.raises(ProviderTransientError):
                provider.generate("hi")

    def test_bad_request_maps_to_invalid_request(self):
        provider = GeminiProvider(api_key="k", model="gemini-1.5-flash")
        mock_resp = _mock_response(400, {"error": {"message": "malformed request"}})
        with patch("app.services.ai.gemini_provider.requests.post", return_value=mock_resp):
            with pytest.raises(ProviderInvalidRequestError):
                provider.generate("hi")

    def test_timeout_maps_to_transient(self):
        provider = GeminiProvider(api_key="k", model="gemini-1.5-flash")
        with patch("app.services.ai.gemini_provider.requests.post", side_effect=requests.Timeout("timed out")):
            with pytest.raises(ProviderTransientError):
                provider.generate("hi")

    def test_unexpected_response_shape_is_invalid_request(self):
        provider = GeminiProvider(api_key="k", model="gemini-1.5-flash")
        mock_resp = _mock_response(200, {"unexpected": "shape"})
        with patch("app.services.ai.gemini_provider.requests.post", return_value=mock_resp):
            with pytest.raises(ProviderInvalidRequestError):
                provider.generate("hi")

    def test_stream_yields_text_chunks(self):
        provider = GeminiProvider(api_key="k", model="gemini-1.5-flash")
        sse_lines = [
            'data: {"candidates": [{"content": {"parts": [{"text": "Hel"}]}}]}',
            'data: {"candidates": [{"content": {"parts": [{"text": "lo"}]}}]}',
        ]
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = sse_lines

        with patch("app.services.ai.gemini_provider.requests.post", return_value=mock_resp):
            chunks = list(provider.stream("hi"))
        assert chunks == ["Hel", "lo"]


# --- Groq (OpenAI-compatible shape) -----------------------------------------
class TestGroqProvider:
    def test_successful_generate(self):
        provider = GroqProvider(api_key="k", model="llama-3.1-70b-versatile")
        mock_resp = _mock_response(200, {
            "choices": [{"message": {"content": "Hello from Groq"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 4, "total_tokens": 6},
        })
        with patch("app.services.ai.groq_provider.requests.post", return_value=mock_resp):
            result = provider.generate("hi")
        assert result.text == "Hello from Groq"
        assert result.total_tokens == 6

    def test_rate_limit(self):
        provider = GroqProvider(api_key="k", model="m")
        mock_resp = _mock_response(429, {"error": {"message": "rate limited"}})
        with patch("app.services.ai.groq_provider.requests.post", return_value=mock_resp):
            with pytest.raises(ProviderRateLimitError):
                provider.generate("hi")


# --- OpenRouter ---------------------------------------------------------------
class TestOpenRouterProvider:
    def test_successful_generate(self):
        provider = OpenRouterProvider(api_key="k", model="openrouter/auto")
        mock_resp = _mock_response(200, {"choices": [{"message": {"content": "Hi from OpenRouter"}}]})
        with patch("app.services.ai.openrouter_provider.requests.post", return_value=mock_resp):
            result = provider.generate("hi")
        assert result.text == "Hi from OpenRouter"

    def test_auth_error(self):
        provider = OpenRouterProvider(api_key="bad", model="m")
        mock_resp = _mock_response(403, {"error": {"message": "forbidden"}})
        with patch("app.services.ai.openrouter_provider.requests.post", return_value=mock_resp):
            with pytest.raises(ProviderAuthError):
                provider.generate("hi")


# --- OpenAI ---------------------------------------------------------------
class TestOpenAIProvider:
    def test_successful_generate(self):
        provider = OpenAIProvider(api_key="k", model="gpt-4o-mini")
        mock_resp = _mock_response(200, {"choices": [{"message": {"content": "Hi from OpenAI"}}]})
        with patch("app.services.ai.openai_provider.requests.post", return_value=mock_resp):
            result = provider.generate("hi")
        assert result.text == "Hi from OpenAI"


# --- Claude (different response shape) -----------------------------------
class TestClaudeProvider:
    def test_successful_generate(self):
        provider = ClaudeProvider(api_key="k", model="claude-sonnet-4-6")
        mock_resp = _mock_response(200, {
            "content": [{"type": "text", "text": "Hello from Claude"}],
            "usage": {"input_tokens": 8, "output_tokens": 12},
        })
        with patch("app.services.ai.claude_provider.requests.post", return_value=mock_resp):
            result = provider.generate("hi")
        assert result.text == "Hello from Claude"
        assert result.prompt_tokens == 8
        assert result.completion_tokens == 12
        assert result.total_tokens == 20

    def test_multi_block_content_concatenated(self):
        provider = ClaudeProvider(api_key="k", model="m")
        mock_resp = _mock_response(200, {
            "content": [
                {"type": "text", "text": "Part one. "},
                {"type": "text", "text": "Part two."},
            ],
        })
        with patch("app.services.ai.claude_provider.requests.post", return_value=mock_resp):
            result = provider.generate("hi")
        assert result.text == "Part one. Part two."

    def test_rate_limit(self):
        provider = ClaudeProvider(api_key="k", model="m")
        mock_resp = _mock_response(429, {"error": {"message": "rate limited"}})
        with patch("app.services.ai.claude_provider.requests.post", return_value=mock_resp):
            with pytest.raises(ProviderRateLimitError):
                provider.generate("hi")
