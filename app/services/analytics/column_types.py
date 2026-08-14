"""
Classifies dataframe columns into numeric / categorical / datetime buckets.

This is intentionally its own module (not buried in the profiler) because
Phase 6 (Automatic EDA) and Phase 7-8 (AI structured context) both need the
same classification to pick chart types / summary stats per column — one
source of truth avoids the two subsystems disagreeing on a column's type.
"""

import pandas as pd

DATE_PARSE_SUCCESS_THRESHOLD = 0.85  # 85%+ of non-null values parse as dates
DATE_SAMPLE_SIZE = 200


def classify_columns(df: pd.DataFrame) -> dict:
    numeric_cols = []
    categorical_cols = []
    datetime_cols = []

    for col in df.columns:
        series = df[col]

        if pd.api.types.is_datetime64_any_dtype(series):
            datetime_cols.append(col)
            continue

        if pd.api.types.is_numeric_dtype(series):
            numeric_cols.append(col)
            continue

        if pd.api.types.is_object_dtype(series) or isinstance(series.dtype, pd.CategoricalDtype):
            if _looks_like_datetime(series):
                datetime_cols.append(col)
            else:
                categorical_cols.append(col)
            continue

        # bool, etc. — treat as categorical by default
        categorical_cols.append(col)

    return {
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "datetime_columns": datetime_cols,
    }


def _looks_like_datetime(series: pd.Series) -> bool:
    sample = series.dropna()
    if sample.empty:
        return False
    sample = sample.sample(min(len(sample), DATE_SAMPLE_SIZE), random_state=0)

    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    success_rate = parsed.notna().mean()
    return success_rate >= DATE_PARSE_SUCCESS_THRESHOLD
