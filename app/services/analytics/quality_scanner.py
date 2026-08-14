"""
Quality scanning runs on the full dataframe (unlike the chunked upload
profiler) because cleaning actions need the complete data in memory anyway
to produce a cleaned copy. This is an explicit, infrequent user action
(not something that runs on every page view), so the memory cost is
acceptable within the 8GB budget for files under the upload size limit.
"""

import pandas as pd

CONSTANT_COLUMN_MAX_UNIQUE = 1
HIGH_CARDINALITY_UNIQUE_RATIO = 0.9
HIGH_CARDINALITY_MIN_ROWS = 20
IQR_MULTIPLIER = 1.5


def scan_quality(df: pd.DataFrame) -> dict:
    n_rows = len(df)

    missing = _scan_missing(df)
    duplicates = _scan_duplicates(df)
    constant_cols = _scan_constant_columns(df)
    high_card_cols = _scan_high_cardinality(df, n_rows)
    outliers = _scan_outliers(df)
    dtype_issues = _scan_dtype_mismatches(df)

    return {
        "row_count": n_rows,
        "column_count": df.shape[1],
        "missing": missing,
        "duplicates": duplicates,
        "constant_columns": constant_cols,
        "high_cardinality_columns": high_card_cols,
        "outliers": outliers,
        "dtype_issues": dtype_issues,
    }


def _scan_missing(df: pd.DataFrame) -> dict:
    counts = df.isna().sum()
    total = len(df)
    per_column = {
        col: {
            "count": int(count),
            "percentage": round(float(count) / total * 100, 2) if total else 0.0,
        }
        for col, count in counts.items()
        if count > 0
    }
    return {
        "total_missing_cells": int(counts.sum()),
        "columns_with_missing": per_column,
    }


def _scan_duplicates(df: pd.DataFrame) -> dict:
    dup_mask = df.duplicated()
    return {
        "count": int(dup_mask.sum()),
        "sample_row_indices": df.index[dup_mask].tolist()[:20],
    }


def _scan_constant_columns(df: pd.DataFrame) -> list:
    constants = []
    for col in df.columns:
        nunique = df[col].nunique(dropna=True)
        if nunique <= CONSTANT_COLUMN_MAX_UNIQUE:
            constants.append(col)
    return constants


def _scan_high_cardinality(df: pd.DataFrame, n_rows: int) -> list:
    if n_rows < HIGH_CARDINALITY_MIN_ROWS:
        return []

    flagged = []
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue  # cardinality checks are for categorical-ish columns
        nunique = df[col].nunique(dropna=True)
        if nunique / n_rows >= HIGH_CARDINALITY_UNIQUE_RATIO:
            flagged.append(col)
    return flagged


def _scan_outliers(df: pd.DataFrame) -> dict:
    result = {}
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        series = df[col].dropna()
        if len(series) < 4:
            continue

        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue

        lower = q1 - IQR_MULTIPLIER * iqr
        upper = q3 + IQR_MULTIPLIER * iqr
        mask = (series < lower) | (series > upper)
        count = int(mask.sum())

        if count > 0:
            result[col] = {
                "count": count,
                "lower_bound": round(float(lower), 4),
                "upper_bound": round(float(upper), 4),
            }
    return result


def _scan_dtype_mismatches(df: pd.DataFrame) -> list:
    """
    Flags object columns where most values actually look numeric — a common
    sign a column was read as text due to a stray non-numeric value (e.g.
    a "N/A" string mixed into an otherwise numeric column).
    """
    flagged = []
    for col in df.columns:
        if not pd.api.types.is_object_dtype(df[col]):
            continue
        sample = df[col].dropna()
        if sample.empty:
            continue
        numeric_coerced = pd.to_numeric(sample, errors="coerce")
        success_rate = numeric_coerced.notna().mean()
        if 0.5 <= success_rate < 1.0:
            flagged.append({
                "column": col,
                "looks_numeric_percentage": round(float(success_rate) * 100, 2),
            })
    return flagged
