"""
Computes descriptive statistics per column, grouped by type (numeric,
categorical, datetime). Reuses classify_columns so this agrees with the
same numeric/categorical/date buckets shown on the dataset detail page.
"""

import pandas as pd

from app.services.analytics.column_types import classify_columns

TOP_CATEGORIES_LIMIT = 10


def compute_descriptive_stats(df: pd.DataFrame) -> dict:
    classification = classify_columns(df)

    numeric_stats = {
        col: _numeric_column_stats(df[col]) for col in classification["numeric_columns"]
    }
    categorical_stats = {
        col: _categorical_column_stats(df[col]) for col in classification["categorical_columns"]
    }
    datetime_stats = {
        col: _datetime_column_stats(df[col]) for col in classification["datetime_columns"]
    }

    return {
        "numeric": numeric_stats,
        "categorical": categorical_stats,
        "datetime": datetime_stats,
        "numeric_columns": classification["numeric_columns"],
        "categorical_columns": classification["categorical_columns"],
        "datetime_columns": classification["datetime_columns"],
    }


def _numeric_column_stats(series: pd.Series) -> dict:
    clean = series.dropna()
    if clean.empty:
        return {"count": 0}

    mode_vals = clean.mode()
    return {
        "count": int(clean.count()),
        "mean": _round(clean.mean()),
        "median": _round(clean.median()),
        "mode": _round(mode_vals.iloc[0]) if not mode_vals.empty else None,
        "std": _round(clean.std()),
        "min": _round(clean.min()),
        "max": _round(clean.max()),
        "q1": _round(clean.quantile(0.25)),
        "q3": _round(clean.quantile(0.75)),
    }


def _categorical_column_stats(series: pd.Series) -> dict:
    clean = series.dropna()
    if clean.empty:
        return {"count": 0, "unique_count": 0, "top_values": []}

    value_counts = clean.value_counts().head(TOP_CATEGORIES_LIMIT)
    top_values = [
        {"value": str(idx), "count": int(count)} for idx, count in value_counts.items()
    ]

    return {
        "count": int(clean.count()),
        "unique_count": int(clean.nunique()),
        "mode": str(clean.mode().iloc[0]) if not clean.mode().empty else None,
        "top_values": top_values,
    }


def _datetime_column_stats(series: pd.Series) -> dict:
    clean = pd.to_datetime(series, errors="coerce").dropna()
    if clean.empty:
        return {"count": 0}

    return {
        "count": int(clean.count()),
        "min": clean.min().isoformat(),
        "max": clean.max().isoformat(),
        "range_days": int((clean.max() - clean.min()).days),
    }


def _round(value, ndigits=4):
    if value is None or pd.isna(value):
        return None
    return round(float(value), ndigits)


def compute_correlation_matrix(df: pd.DataFrame) -> dict:
    classification = classify_columns(df)
    numeric_cols = classification["numeric_columns"]

    if len(numeric_cols) < 2:
        return {"columns": numeric_cols, "matrix": []}

    corr = df[numeric_cols].corr(numeric_only=True).round(4)
    corr = corr.fillna(0)

    return {
        "columns": list(corr.columns),
        "matrix": corr.values.tolist(),
    }
