import json

import pandas as pd
import pytest

from app.services.ai.context_builder import build_dataset_context
from app.services.ai.analyst_service import ask_question, generate_insights
from app.services.ai.base_provider import ProviderResponse


def _sample_df():
    return pd.DataFrame({
        "region": ["north", "south", "north", "south", "east"],
        "revenue": [100, 200, 150, 50, 300],
        "date": pd.to_datetime(
            ["2024-01-01", "2024-01-15", "2024-02-01", "2024-02-15", "2024-03-01"]
        ),
    })


class FakeManager:
    """Minimal stand-in for AIProviderManager — scripts what generate_json,
    generate, and analyze return, so we can test the orchestration logic
    without any real provider or network call."""

    def __init__(self, generate_json_result=None, generate_result=None, analyze_result=None):
        self._generate_json_result = generate_json_result
        self._generate_result = generate_result
        self._analyze_result = analyze_result
        self.generate_json_calls = []
        self.analyze_calls = []
        self.generate_calls = []

    def generate_json(self, prompt, **kwargs):
        self.generate_json_calls.append((prompt, kwargs))
        if isinstance(self._generate_json_result, Exception):
            raise self._generate_json_result
        return self._generate_json_result

    def generate(self, prompt, **kwargs):
        self.generate_calls.append((prompt, kwargs))
        return self._generate_result

    def analyze(self, context, question, **kwargs):
        self.analyze_calls.append((context, question, kwargs))
        return self._analyze_result


# --- context_builder --------------------------------------------------------
def test_build_dataset_context_bounded_and_typed():
    df = _sample_df()
    context = build_dataset_context(df, dataset_name="Sales")

    assert context["dataset_name"] == "Sales"
    assert context["row_count"] == 5
    assert "revenue" in context["numeric_columns"]
    assert "region" in context["categorical_columns"]
    assert "date" in context["datetime_columns"]

    # Never includes raw row data
    assert "rows" not in context
    serialized = json.dumps(context, default=str)
    assert "north" in serialized or "south" in serialized  # top categorical values ok
    assert len(serialized) < 5000  # stays small/bounded


def test_build_dataset_context_numeric_column_has_stats():
    df = _sample_df()
    context = build_dataset_context(df)
    revenue_col = next(c for c in context["columns"] if c["name"] == "revenue")
    assert revenue_col["min"] == 50
    assert revenue_col["max"] == 300


# --- ask_question (planning -> execution -> explanation) -------------------
def test_ask_question_executes_valid_plan_and_grounds_answer():
    manager = FakeManager(
        generate_json_result=ProviderResponse(
            text='{"operation": "aggregate", "column": "revenue", "agg": "sum"}',
            provider="fake", model="m",
            parsed={"operation": "aggregate", "column": "revenue", "agg": "sum"},
        ),
        analyze_result=ProviderResponse(text="Total revenue is 800.", provider="fake", model="m"),
    )
    df = _sample_df()

    result = ask_question(manager, df, "Sales", "What is the total revenue?", user_id=1)

    assert result["computed_result"]["value"] == 800
    assert result["answer"] == "Total revenue is 800."

    # The real computed number must have been passed into analyze()'s context
    passed_context = manager.analyze_calls[0][0]
    assert passed_context["computed_result"]["value"] == 800


def test_ask_question_falls_back_gracefully_on_invalid_plan():
    manager = FakeManager(
        generate_json_result=ProviderResponse(
            text='{"operation": "aggregate", "column": "not_a_real_column", "agg": "sum"}',
            provider="fake", model="m",
            parsed={"operation": "aggregate", "column": "not_a_real_column", "agg": "sum"},
        ),
        analyze_result=ProviderResponse(text="I can describe the dataset overview instead.", provider="fake", model="m"),
    )
    df = _sample_df()

    result = ask_question(manager, df, "Sales", "What is the xyz?", user_id=1)

    assert result["computed_result"] is None
    assert result["answer"] == "I can describe the dataset overview instead."
    # Still called analyze() with a general (non-crashing) context
    passed_context = manager.analyze_calls[0][0]
    assert "computed_result" not in passed_context


def test_ask_question_handles_none_operation():
    manager = FakeManager(
        generate_json_result=ProviderResponse(
            text='{"operation": "none"}', provider="fake", model="m",
            parsed={"operation": "none"},
        ),
        analyze_result=ProviderResponse(text="This dataset has sales by region.", provider="fake", model="m"),
    )
    df = _sample_df()

    result = ask_question(manager, df, "Sales", "What is this dataset about?", user_id=1)
    assert result["computed_result"]["operation"] == "none"
    # "none" results are not injected into the explain context as a "computed_result"
    passed_context = manager.analyze_calls[0][0]
    assert "computed_result" not in passed_context


def test_ask_question_handles_planning_provider_exception():
    manager = FakeManager(
        generate_json_result=RuntimeError("provider exploded"),
        analyze_result=ProviderResponse(text="Fallback answer.", provider="fake", model="m"),
    )
    df = _sample_df()

    result = ask_question(manager, df, "Sales", "anything?", user_id=1)
    assert result["computed_result"] is None
    assert result["answer"] == "Fallback answer."


def test_ask_question_top_n_plan_produces_real_ranking():
    manager = FakeManager(
        generate_json_result=ProviderResponse(
            text="...", provider="fake", model="m",
            parsed={"operation": "top_n", "column": "revenue", "group_by": "region", "agg": "sum", "n": 1},
        ),
        analyze_result=ProviderResponse(text="East leads with 300.", provider="fake", model="m"),
    )
    df = _sample_df()

    result = ask_question(manager, df, "Sales", "Which region has the highest revenue?", user_id=1)
    assert result["computed_result"]["results"][0]["group"] == "east"
    assert result["computed_result"]["results"][0]["value"] == 300


# --- generate_insights -------------------------------------------------------
def test_generate_insights_grounds_facts_in_context():
    manager = FakeManager(
        generate_result=ProviderResponse(text="- East region leads in revenue.", provider="fake", model="m"),
    )
    df = _sample_df()

    result = generate_insights(manager, df, "Sales", user_id=1)

    assert result["insights_text"] == "- East region leads in revenue."
    assert len(result["facts"]) > 0

    passed_context = manager.generate_calls[0][1]["context"]
    assert passed_context["facts"] == result["facts"]


def test_generate_insights_includes_top_and_bottom_performer_facts():
    df = _sample_df()
    manager = FakeManager(generate_result=ProviderResponse(text="ok", provider="fake", model="m"))
    result = generate_insights(manager, df, "Sales", user_id=1)

    fact_types = {f["type"] for f in result["facts"]}
    assert "top_performer" in fact_types or "bottom_performer" in fact_types


def test_generate_insights_handles_no_facts_dataset():
    df = pd.DataFrame({"single_col": [1, 2, 3]})  # not enough structure for facts
    manager = FakeManager(generate_result=ProviderResponse(text="unused", provider="fake", model="m"))

    result = generate_insights(manager, df, "Boring", user_id=1)
    assert result["facts"] == []
    assert "Not enough data" in result["insights_text"]
    assert len(manager.generate_calls) == 0  # never called the AI for an empty fact set
