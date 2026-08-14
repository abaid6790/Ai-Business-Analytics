import pandas as pd
import pytest

from app.services.analytics.eda import compute_descriptive_stats, compute_correlation_matrix
from app.services.analytics.chart_suggestions import suggest_charts
from app.services.analytics.chart_builder import build_chart_data, ChartBuildError, apply_filters


def _sample_df():
    return pd.DataFrame({
        "category": ["a", "b", "a", "b", "a", "c"],
        "amount": [10, 20, 15, 25, 12, 100],
        "region": ["north", "south", "north", "south", "north", "east"],
        "signup_date": pd.to_datetime(
            ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"]
        ),
    })


def test_compute_descriptive_stats_numeric():
    df = _sample_df()
    stats = compute_descriptive_stats(df)
    amount_stats = stats["numeric"]["amount"]

    assert amount_stats["count"] == 6
    assert amount_stats["min"] == 10
    assert amount_stats["max"] == 100
    assert amount_stats["mean"] == pytest.approx(30.333, rel=1e-2)


def test_compute_descriptive_stats_categorical():
    df = _sample_df()
    stats = compute_descriptive_stats(df)
    cat_stats = stats["categorical"]["category"]

    assert cat_stats["unique_count"] == 3
    top_values = {tv["value"]: tv["count"] for tv in cat_stats["top_values"]}
    assert top_values["a"] == 3


def test_compute_descriptive_stats_datetime():
    df = _sample_df()
    stats = compute_descriptive_stats(df)
    date_stats = stats["datetime"]["signup_date"]
    assert date_stats["count"] == 6
    assert date_stats["range_days"] == 5


def test_correlation_matrix_two_numeric_columns():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [2, 4, 6, 8, 10]})
    corr = compute_correlation_matrix(df)
    assert corr["columns"] == ["x", "y"]
    assert corr["matrix"][0][1] == pytest.approx(1.0)


def test_correlation_matrix_insufficient_numeric_columns():
    df = pd.DataFrame({"x": [1, 2, 3], "cat": ["a", "b", "c"]})
    corr = compute_correlation_matrix(df)
    assert corr["matrix"] == []


def test_suggest_charts_includes_histogram_and_bar():
    df = _sample_df()
    stats = compute_descriptive_stats(df)
    suggestions = suggest_charts(stats)

    types = [s["chart_type"] for s in suggestions]
    assert "histogram" in types
    assert "bar" in types


def test_suggest_charts_includes_line_for_date_and_numeric():
    df = _sample_df()
    stats = compute_descriptive_stats(df)
    suggestions = suggest_charts(stats)
    line_charts = [s for s in suggestions if s["chart_type"] == "line"]
    assert len(line_charts) >= 1


def test_build_chart_data_bar_aggregation():
    df = _sample_df()
    result = build_chart_data(df, {
        "chart_type": "bar", "x": "category", "y": "amount", "aggregation": "sum",
    })
    assert result["chart_type"] == "bar"
    assert len(result["labels"]) == 3


def test_build_chart_data_count_without_y():
    df = _sample_df()
    result = build_chart_data(df, {"chart_type": "bar", "x": "region"})
    total = sum(result["datasets"][0]["data"])
    assert total == 6


def test_build_chart_data_grouped():
    df = _sample_df()
    result = build_chart_data(df, {
        "chart_type": "bar", "x": "category", "y": "amount",
        "aggregation": "sum", "group_by": "region",
    })
    assert len(result["datasets"]) >= 1


def test_build_chart_data_scatter():
    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    result = build_chart_data(df, {"chart_type": "scatter", "x": "x", "y": "y"})
    assert result["chart_type"] == "scatter"
    assert len(result["datasets"][0]["data"]) == 3


def test_build_chart_data_histogram():
    df = pd.DataFrame({"x": list(range(100))})
    result = build_chart_data(df, {"chart_type": "histogram", "x": "x"})
    assert sum(result["datasets"][0]["data"]) == 100


def test_build_chart_data_unknown_column_raises():
    df = _sample_df()
    with pytest.raises(ChartBuildError):
        build_chart_data(df, {"chart_type": "bar", "x": "nonexistent"})


def test_build_chart_data_unknown_type_raises():
    df = _sample_df()
    with pytest.raises(ChartBuildError):
        build_chart_data(df, {"chart_type": "not_a_type", "x": "category"})


def test_apply_filters_equals():
    df = _sample_df()
    filtered = apply_filters(df, [{"column": "region", "operator": "equals", "value": "north"}])
    assert (filtered["region"] == "north").all()
    assert len(filtered) == 3


def test_apply_filters_greater_than():
    df = _sample_df()
    filtered = apply_filters(df, [{"column": "amount", "operator": "greater_than", "value": "20"}])
    assert (filtered["amount"] > 20).all()


def test_build_chart_data_with_filters_no_matches_raises():
    df = _sample_df()
    with pytest.raises(ChartBuildError):
        build_chart_data(df, {
            "chart_type": "bar", "x": "category",
            "filters": [{"column": "region", "operator": "equals", "value": "nowhere"}],
        })


def test_apply_filters_unknown_operator_raises():
    df = _sample_df()
    with pytest.raises(ChartBuildError):
        apply_filters(df, [{"column": "amount", "operator": "bogus", "value": "1"}])
