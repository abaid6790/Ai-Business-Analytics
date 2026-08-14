"""
Builds the structured context sent to the AI model. Per spec section 8/24:
never send the raw dataset — send a bounded summary of real, pre-computed
statistics instead. This keeps prompt size predictable, avoids leaking the
full dataset into a third-party API, and is the foundation for "never let
the LLM invent numbers" — anything the model needs to reference must
already be a number we put in front of it.
"""

import pandas as pd

from app.services.analytics.column_types import classify_columns

MAX_TOP_VALUES = 5
MAX_COLUMNS_DESCRIBED = 40


def build_dataset_context(df: pd.DataFrame, dataset_name: str = None) -> dict:
    classification = classify_columns(df)

    columns_summary = []
    for col in list(df.columns)[:MAX_COLUMNS_DESCRIBED]:
        columns_summary.append(_summarize_column(df, col, classification))

    return {
        "dataset_name": dataset_name,
        "row_count": int(len(df)),
        "column_count": int(df.shape[1]),
        "numeric_columns": classification["numeric_columns"],
        "categorical_columns": classification["categorical_columns"],
        "datetime_columns": classification["datetime_columns"],
        "columns": columns_summary,
    }


def _summarize_column(df: pd.DataFrame, col: str, classification: dict) -> dict:
    series = df[col]
    dtype_str = str(series.dtype)

    if col in classification["numeric_columns"]:
        clean = series.dropna()
        return {
            "name": col,
            "type": "numeric",
            "dtype": dtype_str,
            "min": _r(clean.min()) if not clean.empty else None,
            "max": _r(clean.max()) if not clean.empty else None,
            "mean": _r(clean.mean()) if not clean.empty else None,
        }

    if col in classification["datetime_columns"]:
        clean = pd.to_datetime(series, errors="coerce").dropna()
        return {
            "name": col,
            "type": "datetime",
            "dtype": dtype_str,
            "min": clean.min().isoformat() if not clean.empty else None,
            "max": clean.max().isoformat() if not clean.empty else None,
        }

    clean = series.dropna()
    top = clean.value_counts().head(MAX_TOP_VALUES)
    return {
        "name": col,
        "type": "categorical",
        "dtype": dtype_str,
        "unique_count": int(clean.nunique()),
        "top_values": [str(v) for v in top.index.tolist()],
    }


def _r(value, ndigits=4):
    if value is None or pd.isna(value):
        return None
    return round(float(value), ndigits)
