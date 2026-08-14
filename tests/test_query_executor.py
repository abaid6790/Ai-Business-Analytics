import pandas as pd
import pytest

from app.services.analytics.query_executor import (
    QueryPlanError,
    execute_plan,
    validate_plan,
)


def _sample_df():
    return pd.DataFrame({
        "region": ["north", "south", "north", "south", "east"],
        "revenue": [100, 200, 150, 50, 300],
        "category": ["a", "b", "a", "b", "c"],
        "date": pd.to_datetime(
            ["2024-01-01", "2024-01-15", "2024-02-01", "2024-02-15", "2024-03-01"]
        ),
    })


# --- Validation ---------------------------------------------------------
def test_validate_rejects_unknown_operation():
    df = _sample_df()
    with pytest.raises(QueryPlanError):
        validate_plan({"operation": "delete_everything"}, df)


def test_validate_rejects_non_dict_plan():
    df = _sample_df()
    with pytest.raises(QueryPlanError):
        validate_plan("not a dict", df)


def test_validate_none_operation_always_passes():
    df = _sample_df()
    validate_plan({"operation": "none"}, df)  # should not raise


def test_validate_rejects_unknown_column():
    df = _sample_df()
    with pytest.raises(QueryPlanError):
        validate_plan({"operation": "describe_column", "column": "nonexistent"}, df)


def test_validate_rejects_unknown_aggregation():
    df = _sample_df()
    with pytest.raises(QueryPlanError):
        validate_plan({"operation": "aggregate", "column": "revenue", "agg": "hack"}, df)


def test_validate_top_n_requires_group_by():
    df = _sample_df()
    with pytest.raises(QueryPlanError):
        validate_plan({"operation": "top_n", "column": "revenue"}, df)


def test_validate_correlation_requires_both_columns():
    df = _sample_df()
    with pytest.raises(QueryPlanError):
        validate_plan({"operation": "correlation", "column_a": "revenue"}, df)


def test_validate_trend_rejects_bad_frequency():
    df = _sample_df()
    with pytest.raises(QueryPlanError):
        validate_plan({
            "operation": "trend", "date_column": "date", "value_column": "revenue", "freq": "X"
        }, df)


def test_validate_passes_for_well_formed_aggregate():
    df = _sample_df()
    validate_plan({"operation": "aggregate", "column": "revenue", "agg": "sum"}, df)


# --- Execution ------------------------------------------------------------
def test_execute_describe_column_numeric():
    df = _sample_df()
    result = execute_plan({"operation": "describe_column", "column": "revenue"}, df)
    assert result["type"] == "numeric"
    assert result["count"] == 5
    assert result["min"] == 50
    assert result["max"] == 300


def test_execute_describe_column_categorical():
    df = _sample_df()
    result = execute_plan({"operation": "describe_column", "column": "region"}, df)
    assert result["type"] == "categorical"
    assert result["unique_count"] == 3


def test_execute_aggregate_no_group():
    df = _sample_df()
    result = execute_plan({"operation": "aggregate", "column": "revenue", "agg": "sum"}, df)
    assert result["value"] == 800


def test_execute_aggregate_with_group_by():
    df = _sample_df()
    result = execute_plan({
        "operation": "aggregate", "column": "revenue", "agg": "sum", "group_by": "region"
    }, df)
    values = {r["group"]: r["value"] for r in result["results"]}
    assert values["north"] == 250
    assert values["south"] == 250
    assert values["east"] == 300


def test_execute_top_n():
    df = _sample_df()
    result = execute_plan({
        "operation": "top_n", "column": "revenue", "group_by": "region", "agg": "sum", "n": 1
    }, df)
    assert len(result["results"]) == 1
    assert result["results"][0]["group"] == "east"
    assert result["results"][0]["value"] == 300


def test_execute_count_rows_with_filter():
    df = _sample_df()
    result = execute_plan({
        "operation": "count_rows",
        "filters": [{"column": "region", "operator": "equals", "value": "north"}],
    }, df)
    assert result["row_count"] == 2


def test_execute_count_rows_no_filter():
    df = _sample_df()
    result = execute_plan({"operation": "count_rows"}, df)
    assert result["row_count"] == 5


def test_execute_correlation():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [2, 4, 6, 8, 10]})
    result = execute_plan({"operation": "correlation", "column_a": "x", "column_b": "y"}, df)
    assert result["correlation"] == pytest.approx(1.0)


def test_execute_trend():
    df = _sample_df()
    result = execute_plan({
        "operation": "trend", "date_column": "date", "value_column": "revenue", "freq": "M"
    }, df)
    assert len(result["points"]) == 3  # Jan, Feb, Mar


def test_execute_unique_values():
    df = _sample_df()
    result = execute_plan({"operation": "unique_values", "column": "category"}, df)
    assert result["unique_count"] == 3
    values = {v["value"]: v["count"] for v in result["top_values"]}
    assert values["a"] == 2


def test_execute_none_returns_marker():
    df = _sample_df()
    result = execute_plan({"operation": "none"}, df)
    assert result == {"operation": "none"}


def test_execute_with_filters_narrows_aggregate():
    df = _sample_df()
    result = execute_plan({
        "operation": "aggregate", "column": "revenue", "agg": "sum",
        "filters": [{"column": "region", "operator": "equals", "value": "north"}],
    }, df)
    assert result["value"] == 250


def test_execute_filters_matching_nothing_raises():
    df = _sample_df()
    with pytest.raises(QueryPlanError):
        execute_plan({
            "operation": "count_rows",
            "filters": [{"column": "region", "operator": "equals", "value": "nowhere"}],
        }, df)


def test_execute_trend_invalid_dates_raises():
    df = pd.DataFrame({"date": ["not", "a", "date"], "revenue": [1, 2, 3]})
    with pytest.raises(QueryPlanError):
        execute_plan({
            "operation": "trend", "date_column": "date", "value_column": "revenue", "freq": "M"
        }, df)
