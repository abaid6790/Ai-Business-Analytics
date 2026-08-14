"""
Trend and seasonality detection (spec section 15). Kept independent of
the forecasting model choice — the forecaster consults these to decide
which method to use, and the UI shows them as their own summary badges.
"""

import numpy as np
import pandas as pd

MIN_POINTS_FOR_SEASONALITY = 8  # need at least ~2 full cycles for a 4-period season, etc.
SEASONALITY_STRENGTH_THRESHOLD = 0.3


def detect_trend(series: pd.Series) -> dict:
    if len(series) < 2:
        return {"direction": "insufficient_data", "slope": None}

    x = np.arange(len(series))
    y = series.values.astype(float)

    slope, intercept = np.polyfit(x, y, 1)

    mean_abs = np.mean(np.abs(y)) or 1.0
    relative_slope = slope / mean_abs

    if abs(relative_slope) < 0.01:
        direction = "stable"
    elif slope > 0:
        direction = "increasing"
    else:
        direction = "decreasing"

    return {"direction": direction, "slope": round(float(slope), 6)}


def detect_seasonality(series: pd.Series, freq: str) -> dict:
    period = _period_for_freq(freq)

    if period is None or len(series) < max(MIN_POINTS_FOR_SEASONALITY, period * 2):
        return {"detected": False, "period": period, "strength": None}

    try:
        from statsmodels.tsa.seasonal import seasonal_decompose

        decomposition = seasonal_decompose(series, period=period, model="additive", extrapolate_trend="freq")
        seasonal_var = np.var(decomposition.seasonal.dropna())
        residual_var = np.var(decomposition.resid.dropna())
        total_var = seasonal_var + residual_var

        strength = float(seasonal_var / total_var) if total_var > 0 else 0.0
        detected = strength >= SEASONALITY_STRENGTH_THRESHOLD

        return {"detected": detected, "period": period, "strength": round(strength, 4)}
    except Exception:
        return {"detected": False, "period": period, "strength": None}


def _period_for_freq(freq: str):
    return {
        "D": 7,     # weekly cycle
        "W": 52,    # yearly cycle in weeks
        "ME": 12,   # yearly cycle in months
        "QE": 4,    # yearly cycle in quarters
        "YE": None,  # no shorter cycle to detect
    }.get(freq)
