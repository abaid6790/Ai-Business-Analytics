"""
Automatic classification/regression detection (spec section 12).

Heuristic: a numeric target with many distinct values is regression; a
target that's non-numeric, boolean, or numeric-but-low-cardinality (e.g.
a 0/1 flag, a 1-5 rating) is classification.
"""

import pandas as pd

MAX_CLASSIFICATION_CARDINALITY = 20


class TaskDetectionError(Exception):
    pass


def detect_task_type(series: pd.Series) -> str:
    clean = series.dropna()
    if clean.empty:
        raise TaskDetectionError("Target column has no non-missing values.")

    if pd.api.types.is_bool_dtype(clean):
        return "classification"

    if pd.api.types.is_numeric_dtype(clean):
        nunique = clean.nunique()
        if nunique <= MAX_CLASSIFICATION_CARDINALITY:
            return "classification"
        return "regression"

    return "classification"
