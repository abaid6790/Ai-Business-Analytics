"""
Turns a raw (date_column, value_column) pair into a clean, regularly
spaced pandas Series indexed by date — resampled and aggregated so gaps,
duplicate dates, and irregular spacing don't break the forecasting models
downstream (spec section 15: date detection + historical visualization).
"""

import pandas as pd

MIN_POINTS_FOR_FORECAST = 4

FREQ_LABELS = {"D": "daily", "W": "weekly", "ME": "monthly", "QE": "quarterly", "YE": "yearly"}


class TimeSeriesError(Exception):
    pass


def prepare_series(df: pd.DataFrame, date_column: str, value_column: str, freq: str = None, agg: str = "sum") -> dict:
    if date_column not in df.columns:
        raise TimeSeriesError(f"Column '{date_column}' not found.")
    if value_column not in df.columns:
        raise TimeSeriesError(f"Column '{value_column}' not found.")

    sub = df[[date_column, value_column]].copy()
    sub[date_column] = pd.to_datetime(sub[date_column], errors="coerce")
    sub[value_column] = pd.to_numeric(sub[value_column], errors="coerce")
    sub = sub.dropna()

    if len(sub) < MIN_POINTS_FOR_FORECAST:
        raise TimeSeriesError(
            f"Not enough valid date/value pairs to forecast (found {len(sub)}, need at least {MIN_POINTS_FOR_FORECAST})."
        )

    sub = sub.sort_values(date_column)

    resolved_freq = freq or _infer_frequency(sub[date_column])
    series = sub.set_index(date_column)[value_column].resample(resolved_freq).agg(agg)

    # Interior gaps (e.g. a month with zero transactions) become 0 after
    # resample+sum; that's a real value, not missing data, so we don't
    # impute — but a fully-empty resampled bucket from resample() itself
    # is filled at 0 by `agg`, which is the correct behavior for "sum".
    series = series.fillna(0)

    if len(series) < MIN_POINTS_FOR_FORECAST:
        raise TimeSeriesError("Not enough distinct time periods to forecast after resampling.")

    return {
        "series": series,
        "freq": resolved_freq,
        "freq_label": FREQ_LABELS.get(resolved_freq, resolved_freq),
    }


def _infer_frequency(date_series: pd.Series) -> str:
    unique_dates = date_series.drop_duplicates().sort_values()
    inferred = pd.infer_freq(unique_dates)
    if inferred:
        # Normalize common aliases to the ones we support downstream.
        base = inferred[0]
        mapping = {"D": "D", "W": "W", "M": "ME", "Q": "QE", "A": "YE", "Y": "YE"}
        if base in mapping:
            return mapping[base]

    # Fallback: infer from the median gap between consecutive dates.
    diffs = unique_dates.diff().dropna()
    if diffs.empty:
        return "D"
    median_days = diffs.dt.days.median()

    if median_days <= 1:
        return "D"
    if median_days <= 8:
        return "W"
    if median_days <= 45:
        return "ME"
    if median_days <= 135:
        return "QE"
    return "YE"
