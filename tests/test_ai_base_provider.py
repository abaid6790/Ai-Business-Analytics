import pytest

from app.services.ai.base_provider import (
    BaseAIProvider,
    ProviderInvalidRequestError,
    ProviderResponse,
)


class FakeProvider(BaseAIProvider):
    name = "fake"

    def __init__(self, response_text="hello", tokens=None, raise_on_send=None):
        super().__init__(api_key="fake-key", model="fake-model")
        self.response_text = response_text
        self.tokens = tokens or {}
        self.raise_on_send = raise_on_send
        self.send_calls = []

    def _send(self, prompt, **kwargs):
        self.send_calls.append(prompt)
        if self.raise_on_send:
            raise self.raise_on_send
        return {"text": self.response_text, **self.tokens}


def test_generate_returns_provider_response():
    provider = FakeProvider(response_text="the answer is 42")
    result = provider.generate("what is the answer?")

    assert isinstance(result, ProviderResponse)
    assert result.text == "the answer is 42"
    assert result.provider == "fake"
    assert result.model == "fake-model"


def test_generate_json_parses_clean_json():
    provider = FakeProvider(response_text='{"total": 100, "label": "sales"}')
    result = provider.generate_json("give me totals")
    assert result.parsed == {"total": 100, "label": "sales"}


def test_generate_json_strips_code_fences():
    provider = FakeProvider(response_text='```json\n{"x": 1}\n```')
    result = provider.generate_json("give me json")
    assert result.parsed == {"x": 1}


def test_generate_json_raises_on_invalid_json():
    provider = FakeProvider(response_text="not json at all")
    with pytest.raises(ProviderInvalidRequestError):
        provider.generate_json("give me json")


def test_generate_json_includes_json_instruction_in_prompt():
    provider = FakeProvider(response_text="{}")
    provider.generate_json("original question")
    assert "original question" in provider.send_calls[0]
    assert "JSON" in provider.send_calls[0]


def test_analyze_includes_context_and_question():
    provider = FakeProvider(response_text="Revenue grew 10%.")
    result = provider.analyze({"total_revenue": 1000}, "How did revenue change?")

    assert "1000" in provider.send_calls[0]
    assert "How did revenue change?" in provider.send_calls[0]
    assert result.text == "Revenue grew 10%."


def test_analyze_instructs_not_to_invent_numbers():
    provider = FakeProvider(response_text="ok")
    provider.analyze({"x": 1}, "question")
    assert "do not invent" in provider.send_calls[0].lower()


def test_stream_default_fallback_yields_full_text_once():
    provider = FakeProvider(response_text="full response")
    chunks = list(provider.stream("a prompt"))
    assert chunks == ["full response"]


def test_response_tokens_populated_from_send_result():
    provider = FakeProvider(
        response_text="hi",
        tokens={"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
    )
    result = provider.generate("prompt")
    assert result.prompt_tokens == 5
    assert result.completion_tokens == 10
    assert result.total_tokens == 15
