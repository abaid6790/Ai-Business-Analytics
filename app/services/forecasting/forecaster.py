"""
Generates a future forecast from a prepared time series. Method selection
is automatic and honest about its own limits (spec section 15: "Support
lightweight models suitable for the user's hardware" — no GPU, no heavy
dependency beyond statsmodels, which is pure CPU and already a common
Pandas-ecosystem library):

  - Enough history + detected seasonality -> Holt-Winters (trend + seasonal)
  - Enough history, no seasonality -> Holt's linear trend
  - Too little history for either -> simple linear regression extrapolation,
    clearly labeled as a fallback rather than silently pretending it's a
    full exponential-smoothing model.

Confidence intervals are approximate (residual-std based, widening with
forecast horizon) rather than statsmodels' exact prediction intervals —
labeled as such in the result so the UI never overstates precision.
"""

import numpy as np
import pandas as pd

from app.services.forecasting.trend_seasonality import detect_seasonality, detect_trend

MIN_POINTS_FOR_HOLT_WINTERS_MULTIPLIER = 2
MIN_POINTS_FOR_HOLT_LINEAR = 6
CONFIDENCE_Z = 1.96


class ForecastError(Exception):
    pass


def generate_forecast(series: pd.Series, freq: str, periods: int) -> dict:
    if periods < 1 or periods > 120:
        raise ForecastError("Forecast horizon must be between 1 and 120 periods.")

    trend = detect_trend(series)
    seasonality = detect_seasonality(series, freq)

    method, forecast_values, resid_std = _fit_and_forecast(series, seasonality, periods)

    future_index = _build_future_index(series.index, freq, periods)
    forecast_points = _build_forecast_points(future_index, forecast_values, resid_std)

    return {
        "history": [
            {"date": idx.isoformat(), "value": round(float(v), 4)} for idx, v in series.items()
        ],
        "forecast": forecast_points,
        "trend": trend,
        "seasonality": seasonality,
        "method": method,
        "confidence_method": "approximate (residual std, widening with horizon)",
    }


def _fit_and_forecast(series, seasonality, periods):
    n = len(series)

    if seasonality["detected"] and n >= seasonality["period"] * MIN_POINTS_FOR_HOLT_WINTERS_MULTIPLIER:
        try:
            return _holt_winters_seasonal(series, seasonality["period"], periods)
        except Exception:
            pass

    if n >= MIN_POINTS_FOR_HOLT_LINEAR:
        try:
            return _holt_linear_trend(series, periods)
        except Exception:
            pass

    return _linear_regression_fallback(series, periods)


def _holt_winters_seasonal(series, period, periods):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    model = ExponentialSmoothing(
        series, trend="add", seasonal="add", seasonal_periods=period, initialization_method="estimated"
    )
    fitted = model.fit()
    forecast = fitted.forecast(periods)
    resid_std = float(np.std(fitted.resid))
    return "holt_winters_seasonal", forecast.values, resid_std


def _holt_linear_trend(series, periods):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    model = ExponentialSmoothing(series, trend="add", seasonal=None, initialization_method="estimated")
    fitted = model.fit()
    forecast = fitted.forecast(periods)
    resid_std = float(np.std(fitted.resid))
    return "holt_linear_trend", forecast.values, resid_std


def _linear_regression_fallback(series, periods):
    x = np.arange(len(series))
    y = series.values.astype(float)
    slope, intercept = np.polyfit(x, y, 1)

    future_x = np.arange(len(series), len(series) + periods)
    forecast_values = slope * future_x + intercept

    residuals = y - (slope * x + intercept)
    resid_std = float(np.std(residuals)) if len(residuals) > 1 else 0.0

    return "linear_regression_fallback", forecast_values, resid_std


def _build_future_index(history_index, freq, periods):
    return pd.date_range(start=history_index[-1], periods=periods + 1, freq=freq)[1:]


def _build_forecast_points(future_index, forecast_values, resid_std):
    points = []
    for step, (idx, value) in enumerate(zip(future_index, forecast_values), start=1):
        margin = CONFIDENCE_Z * resid_std * np.sqrt(step)
        points.append({
            "date": idx.isoformat(),
            "value": round(float(value), 4),
            "lower": round(float(value - margin), 4),
            "upper": round(float(value + margin), 4),
        })
    return points
