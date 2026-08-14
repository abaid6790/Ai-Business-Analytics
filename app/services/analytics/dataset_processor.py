"""
Reads CSV/XLSX/XLS files and computes the metadata shown in spec section 4:
row/column counts, missing values, duplicate rows, dtypes, memory usage,
and numeric/categorical/date column breakdowns.

Two code paths, chosen by file size (spec section 31 — 8GB RAM budget):
  - Small/medium files: read fully into memory once, compute exact stats.
  - Large files: chunked reads accumulate row counts and missing-value
    counts without ever holding the whole file in memory. Duplicate
    detection is skipped for chunked files (flagged in the result) since
    exact duplicate detection needs the whole dataset in memory or a
    hashing pass we don't do yet.
"""

import json
import os

import pandas as pd

from app.services.analytics.column_types import classify_columns


class DatasetProfilingError(Exception):
    pass


def read_full_dataframe(path: str, file_type: str) -> pd.DataFrame:
    """Public wrapper around _read_full for callers outside this module
    (e.g. the data-cleaning service, which always needs the full frame)."""
    return _read_full(path, file_type)


def _read_full(path: str, file_type: str) -> pd.DataFrame:
    try:
        if file_type == "csv":
            return pd.read_csv(path)
        return pd.read_excel(path, engine="openpyxl" if file_type == "xlsx" else None)
    except Exception as exc:  # noqa: BLE001 - surface as a user-facing error
        raise DatasetProfilingError(f"Could not parse file: {exc}") from exc


def read_preview_rows(path: str, file_type: str, n_rows: int) -> dict:
    """Fast, cheap read of just the first N rows for the preview table."""
    try:
        if file_type == "csv":
            df = pd.read_csv(path, nrows=n_rows)
        else:
            df = pd.read_excel(
                path, nrows=n_rows, engine="openpyxl" if file_type == "xlsx" else None
            )
    except Exception as exc:  # noqa: BLE001
        raise DatasetProfilingError(f"Could not parse file: {exc}") from exc

    if df.shape[1] == 0:
        raise DatasetProfilingError("The file has no columns.")

    return {
        "columns": list(df.columns.astype(str)),
        "rows": json.loads(df.head(n_rows).to_json(orient="records", date_format="iso")),
    }


def profile_dataset(path: str, file_type: str, full_profile_max_bytes: int) -> dict:
    """
    Returns a dict of computed metadata matching the Dataset model's
    metadata fields. Raises DatasetProfilingError on unparseable files.
    """
    file_size_bytes = os.path.getsize(path)

    if file_size_bytes <= full_profile_max_bytes or file_type != "csv":
        # XLSX has no cheap chunked-read path via openpyxl/pandas, so we
        # always full-load Excel files regardless of size threshold.
        return _profile_full(path, file_type)

    return _profile_chunked(path)


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Computes the same stats dict as _profile_full, but from an
    already-loaded dataframe — used after cleaning, where we already have
    the cleaned frame in memory and don't want to write-then-reread it."""
    if df.shape[1] == 0:
        raise DatasetProfilingError("The file has no columns.")
    if df.shape[0] == 0:
        raise DatasetProfilingError("The cleaned dataset has no rows left.")

    classification = classify_columns(df)
    dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}

    return {
        "row_count": int(df.shape[0]),
        "column_count": int(df.shape[1]),
        "missing_values_count": int(df.isna().sum().sum()),
        "duplicate_rows_count": int(df.duplicated().sum()),
        "memory_usage_bytes": int(df.memory_usage(deep=True).sum()),
        "dtypes_json": json.dumps(dtypes),
        "numeric_columns": classification["numeric_columns"],
        "categorical_columns": classification["categorical_columns"],
        "datetime_columns": classification["datetime_columns"],
        "duplicate_detection_skipped": False,
    }


def _profile_full(path: str, file_type: str) -> dict:
    df = _read_full(path, file_type)
    return profile_dataframe(df)


def _profile_chunked(path: str, chunk_size: int = 50_000) -> dict:
    row_count = 0
    missing_counts = None
    dtypes = None
    columns = None
    first_chunk_df = None

    try:
        reader = pd.read_csv(path, chunksize=chunk_size)
        for chunk in reader:
            if columns is None:
                columns = list(chunk.columns.astype(str))
                dtypes = {col: str(dtype) for col, dtype in chunk.dtypes.items()}
                missing_counts = chunk.isna().sum()
                first_chunk_df = chunk
            else:
                missing_counts = missing_counts.add(chunk.isna().sum(), fill_value=0)
            row_count += len(chunk)
    except Exception as exc:  # noqa: BLE001
        raise DatasetProfilingError(f"Could not parse file: {exc}") from exc

    if columns is None or row_count == 0:
        raise DatasetProfilingError("The file has no data rows.")

    classification = classify_columns(first_chunk_df)
    file_size_bytes = os.path.getsize(path)

    return {
        "row_count": int(row_count),
        "column_count": len(columns),
        "missing_values_count": int(missing_counts.sum()),
        "duplicate_rows_count": None,  # not computed for large files
        "memory_usage_bytes": file_size_bytes,  # best-effort estimate
        "dtypes_json": json.dumps(dtypes),
        "numeric_columns": classification["numeric_columns"],
        "categorical_columns": classification["categorical_columns"],
        "datetime_columns": classification["datetime_columns"],
        "duplicate_detection_skipped": True,
    }
