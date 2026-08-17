"""
Orchestrates a single user question end to end:

  1. Ask the AI for a structured "plan" describing what computation would
     answer the question (generate_json) — the AI never touches the data
     directly, it only names an operation + column(s) from a whitelist.
  2. Validate the plan against the actual dataframe (query_executor).
  3. Execute the plan with plain Pandas — this is where the real number
     comes from, not the AI.
  4. Ask the AI to explain the result in plain language (analyze()),
     handing it ONLY the computed numbers as context, with an explicit
     instruction not to invent anything beyond them.

If step 1 produces an invalid plan (unknown column, malformed JSON), we
don't guess — we fall back to a "general" answer grounded in the bounded
dataset summary instead of a specific computed figure.
"""

import json

import pandas as pd

from app.services.ai.context_builder import build_dataset_context
from app.services.analytics.query_executor import (
    QueryPlanError,
    execute_plan,
    validate_plan,
)

PLANNING_INSTRUCTIONS = """You are a planning assistant for a data analysis tool. Given a user's \
question about a dataset, decide which single operation would compute the answer.

Respond with ONLY a JSON object matching one of these shapes:
{{"operation": "describe_column", "column": "<column name>"}}
{{"operation": "aggregate", "column": "<numeric column>", "agg": "sum|mean|count|min|max|median", "group_by": "<column or null>"}}
{{"operation": "top_n", "column": "<numeric column>", "group_by": "<column>", "agg": "sum|mean|count|min|max|median", "n": <int>, "ascending": false}}
{{"operation": "count_rows", "filters": [{{"column": "...", "operator": "equals|not_equals|greater_than|less_than|contains", "value": "..."}}]}}
{{"operation": "correlation", "column_a": "<numeric column>", "column_b": "<numeric column>"}}
{{"operation": "trend", "date_column": "<datetime column>", "value_column": "<numeric column>", "freq": "D|W|M|Y", "agg": "sum|mean"}}
{{"operation": "unique_values", "column": "<categorical column>"}}
{{"operation": "none"}}

Use "none" only if the question is conceptual and doesn't need a specific computed number \
(e.g. "what kind of data is this?").

Available columns and types:
{columns_description}

Only ever reference column names from the list above, exactly as spelled. Never invent a column.

Question: {question}"""


def _format_columns_for_prompt(context: dict) -> str:
    lines = []
    for col in context["columns"]:
        lines.append(f"- {col['name']} ({col['type']})")
    return "\n".join(lines)


def _plan_and_compute(provider_manager, df: pd.DataFrame, dataset_name: str, question: str, user_id=None) -> dict:
    """
    Runs steps 1-3 (plan -> validate -> execute) and builds the bounded
    context that step 4 (explanation) will be grounded in. Shared by both
    the blocking `ask_question()` and the streaming `prepare_stream()`
    paths below, so the "never invent a number" pipeline only exists in
    one place.

    Returns {"explain_context": dict, "plan": dict|None, "computed_result": dict|None}.
    """
    context = build_dataset_context(df, dataset_name=dataset_name)

    planning_prompt = PLANNING_INSTRUCTIONS.format(
        columns_description=_format_columns_for_prompt(context),
        question=question,
    )

    plan = None
    computed_result = None

    try:
        plan_response = provider_manager.generate_json(
            planning_prompt, user_id=user_id, use_cache=True,
            context={"kind": "plan", "dataset": dataset_name, "question": question},
        )
        plan = plan_response.parsed
        validate_plan(plan, df)
        computed_result = execute_plan(plan, df)
    except QueryPlanError:
        plan = None
        computed_result = None
    except Exception:
        # Any planning/parsing failure (bad JSON, provider error surfaced
        # from generate_json, etc.) falls back to a general answer rather
        # than propagating — the user still gets something useful.
        plan = None
        computed_result = None

    explain_context = {
        "dataset_overview": {
            "row_count": context["row_count"],
            "column_count": context["column_count"],
            "numeric_columns": context["numeric_columns"],
            "categorical_columns": context["categorical_columns"],
            "datetime_columns": context["datetime_columns"],
        },
    }
    if computed_result and computed_result.get("operation") != "none":
        explain_context["computed_result"] = computed_result

    return {"explain_context": explain_context, "plan": plan, "computed_result": computed_result}


def ask_question(provider_manager, df: pd.DataFrame, dataset_name: str, question: str, user_id=None) -> dict:
    """
    Returns {"answer": str, "computed_result": dict|None, "plan": dict|None}.
    """
    planned = _plan_and_compute(provider_manager, df, dataset_name, question, user_id)

    answer_response = provider_manager.analyze(
        planned["explain_context"], question, user_id=user_id, use_cache=False,
    )

    return {
        "answer": answer_response.text,
        "computed_result": planned["computed_result"],
        "plan": planned["plan"],
    }


def prepare_stream(provider_manager, df: pd.DataFrame, dataset_name: str, question: str, user_id=None) -> dict:
    """
    Runs the plan -> validate -> execute steps synchronously (fast — no
    reason to stream Pandas execution), and returns everything the caller
    needs to *then* stream just the final explanation via
    `provider_manager.stream_analyze(explain_context, question, ...)`.

    Splitting it this way (rather than making the whole pipeline one
    generator) is what lets the route persist `computed_result` alongside
    the eventually-accumulated streamed text, since a generator can't also
    return a value once it starts yielding.
    """
    return _plan_and_compute(provider_manager, df, dataset_name, question, user_id)


# ---------------------------------------------------------------------------
# Automatic insights (spec section 10)
# ---------------------------------------------------------------------------
INSIGHT_FACT_LIMIT = 8

INSIGHTS_INSTRUCTIONS = """You are a business analyst. Below is a list of pre-computed facts about \
a dataset. Turn them into a short list of clear, plain-language business insights — trends, \
notable comparisons, and anything a business user should know.

RULES:
- Only reference numbers that appear in the facts below. Do not invent, estimate, or round \
differently than given.
- Write 3-6 short bullet points.
- No preamble, no markdown headers — just the bullet points.

FACTS:
{facts}
"""


def generate_insights(provider_manager, df: pd.DataFrame, dataset_name: str, user_id=None) -> dict:
    """Computes a handful of real facts (top category, trend, outlier count,
    strongest correlation) and asks the AI to phrase them as insights —
    every number in the output traces back to something in `facts`."""
    facts = _compute_insight_facts(df)

    if not facts:
        return {"insights_text": "Not enough data in this dataset to generate insights.", "facts": []}

    prompt = INSIGHTS_INSTRUCTIONS.format(facts=json.dumps(facts, default=str, indent=2))
    response = provider_manager.generate(
        prompt, user_id=user_id, use_cache=True,
        context={"kind": "insights", "dataset": dataset_name, "facts": facts},
    )

    return {"insights_text": response.text, "facts": facts}


def _compute_insight_facts(df: pd.DataFrame) -> list:
    from app.services.analytics.column_types import classify_columns
    from app.services.analytics.eda import compute_correlation_matrix
    from app.services.analytics.quality_scanner import scan_quality

    classification = classify_columns(df)
    numeric_cols = classification["numeric_columns"]
    categorical_cols = classification["categorical_columns"]
    datetime_cols = classification["datetime_columns"]

    facts = []

    if numeric_cols and categorical_cols:
        value_col, group_col = numeric_cols[0], categorical_cols[0]
        try:
            grouped = df.groupby(group_col)[value_col].sum().sort_values(ascending=False)
            if len(grouped) >= 2:
                facts.append({
                    "type": "top_performer",
                    "detail": f"Highest total {value_col} by {group_col}",
                    "group": str(grouped.index[0]),
                    "value": _r(grouped.iloc[0]),
                })
                facts.append({
                    "type": "bottom_performer",
                    "detail": f"Lowest total {value_col} by {group_col}",
                    "group": str(grouped.index[-1]),
                    "value": _r(grouped.iloc[-1]),
                })
        except Exception:
            pass

    if datetime_cols and numeric_cols:
        date_col, value_col = datetime_cols[0], numeric_cols[0]
        try:
            sub = df[[date_col, value_col]].copy()
            sub[date_col] = pd.to_datetime(sub[date_col], errors="coerce")
            sub = sub.dropna(subset=[date_col]).sort_values(date_col)
            if len(sub) >= 2:
                first_half = sub.iloc[: len(sub) // 2][value_col].sum()
                second_half = sub.iloc[len(sub) // 2:][value_col].sum()
                if first_half:
                    pct_change = round((second_half - first_half) / abs(first_half) * 100, 2)
                    facts.append({
                        "type": "trend",
                        "detail": f"{value_col} change from first half to second half of the date range",
                        "first_half_total": _r(first_half),
                        "second_half_total": _r(second_half),
                        "percent_change": pct_change,
                    })
        except Exception:
            pass

    if len(numeric_cols) >= 2:
        try:
            corr = compute_correlation_matrix(df)
            best = None
            for i, col_a in enumerate(corr["columns"]):
                for j, col_b in enumerate(corr["columns"]):
                    if j <= i:
                        continue
                    value = corr["matrix"][i][j]
                    if best is None or abs(value) > abs(best["correlation"]):
                        best = {"column_a": col_a, "column_b": col_b, "correlation": value}
            if best and abs(best["correlation"]) >= 0.3:
                facts.append({"type": "correlation", **best})
        except Exception:
            pass

    try:
        quality = scan_quality(df)
        if quality["outliers"]:
            worst_col = max(quality["outliers"].items(), key=lambda kv: kv[1]["count"])
            facts.append({
                "type": "anomaly",
                "detail": f"Outliers detected in {worst_col[0]}",
                "column": worst_col[0],
                "count": worst_col[1]["count"],
            })
        if quality["duplicates"]["count"] > 0:
            facts.append({
                "type": "data_quality",
                "detail": "Duplicate rows present",
                "count": quality["duplicates"]["count"],
            })
    except Exception:
        pass

    return facts[:INSIGHT_FACT_LIMIT]


def _r(value, ndigits=4):
    if value is None or pd.isna(value):
        return None
    return round(float(value), ndigits)
