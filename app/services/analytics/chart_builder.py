"""
Builds Chart.js-ready {labels, datasets} JSON from a chart spec. This is
the one place that turns "x column, y column, chart type, aggregation,
grouping, filters" into actual numbers — both the automatic EDA charts and
the interactive chart builder go through this same function, so they never
disagree on how a bar/line/scatter chart is computed.
"""

import numpy as np
import pandas as pd

AGGREGATIONS = {"sum", "mean", "count", "min", "max", "median"}
CHART_TYPES = {"bar", "line", "area", "scatter", "pie", "doughnut", "histogram"}
MAX_CATEGORIES = 50
HISTOGRAM_BINS = 20


class ChartBuildError(Exception):
    pass


def apply_filters(df: pd.DataFrame, filters: list) -> pd.DataFrame:
    """
    filters: list of {column, operator, value}. Operators are whitelisted —
    no arbitrary query strings are ever evaluated against the dataframe.
    """
    for f in filters or []:
        column = f.get("column")
        operator = f.get("operator")
        value = f.get("value")

        if column not in df.columns:
            raise ChartBuildError(f"Unknown filter column: {column}")

        series = df[column]

        if operator == "equals":
            df = df[series.astype(str) == str(value)]
        elif operator == "not_equals":
            df = df[series.astype(str) != str(value)]
        elif operator == "greater_than":
            df = df[pd.to_numeric(series, errors="coerce") > float(value)]
        elif operator == "less_than":
            df = df[pd.to_numeric(series, errors="coerce") < float(value)]
        elif operator == "contains":
            df = df[series.astype(str).str.contains(str(value), case=False, na=False)]
        else:
            raise ChartBuildError(f"Unknown filter operator: {operator}")

    return df


def build_chart_data(df: pd.DataFrame, spec: dict) -> dict:
    chart_type = spec.get("chart_type")
    x = spec.get("x")
    y = spec.get("y")
    aggregation = spec.get("aggregation") or "sum"
    group_by = spec.get("group_by")
    filters = spec.get("filters") or []

    if chart_type not in CHART_TYPES:
        raise ChartBuildError(f"Unsupported chart type: {chart_type}")
    if x and x not in df.columns:
        raise ChartBuildError(f"Column not found: {x}")
    if y and y not in df.columns:
        raise ChartBuildError(f"Column not found: {y}")
    if group_by and group_by not in df.columns:
        raise ChartBuildError(f"Column not found: {group_by}")
    if aggregation not in AGGREGATIONS:
        raise ChartBuildError(f"Unsupported aggregation: {aggregation}")

    df = apply_filters(df, filters)
    if df.empty:
        raise ChartBuildError("No rows match the selected filters.")

    if chart_type == "histogram":
        return _build_histogram(df, x)
    if chart_type == "scatter":
        return _build_scatter(df, x, y)
    if chart_type in ("pie", "doughnut"):
        return _build_pie(df, x, y, aggregation)
    if group_by:
        return _build_grouped(df, x, y, aggregation, group_by, chart_type)
    return _build_simple(df, x, y, aggregation, chart_type)


def _build_histogram(df: pd.DataFrame, x: str) -> dict:
    series = pd.to_numeric(df[x], errors="coerce").dropna()
    if series.empty:
        raise ChartBuildError(f"Column '{x}' has no numeric data to plot.")

    counts, edges = np.histogram(series, bins=HISTOGRAM_BINS)
    labels = [f"{edges[i]:.2f}\u2013{edges[i+1]:.2f}" for i in range(len(edges) - 1)]

    return {
        "labels": labels,
        "datasets": [{"label": x, "data": counts.tolist()}],
        "chart_type": "bar",
    }


def _build_scatter(df: pd.DataFrame, x: str, y: str) -> dict:
    if not y:
        raise ChartBuildError("Scatter plots need both an X and a Y column.")
    sub = df[[x, y]].dropna()
    sub_x = pd.to_numeric(sub[x], errors="coerce")
    sub_y = pd.to_numeric(sub[y], errors="coerce")
    points = [
        {"x": px, "y": py}
        for px, py in zip(sub_x.tolist(), sub_y.tolist())
        if px == px and py == py  # drop NaN (NaN != NaN)
    ]
    return {
        "labels": [],
        "datasets": [{"label": f"{x} vs {y}", "data": points}],
        "chart_type": "scatter",
    }


def _build_pie(df: pd.DataFrame, x: str, y: str, aggregation: str) -> dict:
    grouped = _aggregate(df, x, y, aggregation)
    grouped = grouped.head(MAX_CATEGORIES)
    return {
        "labels": [str(v) for v in grouped.index.tolist()],
        "datasets": [{"label": y or "count", "data": grouped.values.tolist()}],
        "chart_type": "pie",
    }


def _build_grouped(df: pd.DataFrame, x: str, y: str, aggregation: str, group_by: str, chart_type: str) -> dict:
    if not y:
        raise ChartBuildError("Grouped charts need a Y column to aggregate.")

    pivot = df.groupby([x, group_by])[y].agg(aggregation).unstack(fill_value=0)
    pivot = pivot.head(MAX_CATEGORIES)

    labels = [str(v) for v in pivot.index.tolist()]
    datasets = [
        {"label": str(col), "data": pivot[col].tolist()}
        for col in pivot.columns
    ]
    return {"labels": labels, "datasets": datasets, "chart_type": chart_type}


def _build_simple(df: pd.DataFrame, x: str, y: str, aggregation: str, chart_type: str) -> dict:
    grouped = _aggregate(df, x, y, aggregation)
    grouped = grouped.head(MAX_CATEGORIES)
    return {
        "labels": [str(v) for v in grouped.index.tolist()],
        "datasets": [{"label": y or "count", "data": grouped.values.tolist()}],
        "chart_type": chart_type,
    }


def _aggregate(df: pd.DataFrame, x: str, y: str, aggregation: str) -> pd.Series:
    if y:
        grouped = df.groupby(x)[y].agg(aggregation)
    else:
        grouped = df.groupby(x).size()
    return grouped.sort_values(ascending=False) if aggregation != "count" else grouped
