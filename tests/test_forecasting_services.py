import numpy as np
import pandas as pd
import pytest

from app.services.forecasting.preparer import prepare_series, TimeSeriesError
from app.services.forecasting.trend_seasonality import detect_trend, detect_seasonality
from app.services.forecasting.forecaster import generate_forecast, ForecastError


def _monthly_trend_seasonal_df(n=36, trend_slope=50, seasonal_amplitude=200, noise=20, seed=0):
    dates = pd.date_range("2021-01-01", periods=n, freq="ME")
    rng = np.random.RandomState(seed)
    trend = np.arange(n) * trend_slope
    seasonal = seasonal_amplitude * np.sin(np.arange(n) * 2 * np.pi / 12)
    values = 1000 + trend + seasonal + rng.normal(0, noise, n)
    return pd.DataFrame({"date": dates, "value": values})


def _daily_flat_df(n=10):
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({"date": dates, "value": [100.0] * n})


def test_prepare_series_infers_monthly_frequency():
    df = _monthly_trend_seasonal_df()
    result = prepare_series(df, "date", "value")
    assert result["freq"] == "ME"
    assert result["freq_label"] == "monthly"
    assert len(result["series"]) == 36


def test_prepare_series_rejects_missing_column():
    df = _daily_flat_df()
    with pytest.raises(TimeSeriesError):
        prepare_series(df, "nonexistent", "value")


def test_prepare_series_rejects_too_few_points():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=2), "value": [1, 2]})
    with pytest.raises(TimeSeriesError):
        prepare_series(df, "date", "value")


def test_prepare_series_drops_unparseable_dates_and_values():
    df = pd.DataFrame({
        "date": ["2024-01-01", "not-a-date", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"],
        "value": [1, 2, "not-numeric", 4, 5, 6],
    })
    result = prepare_series(df, "date", "value")
    # 2 invalid rows dropped -> 4 valid rows spanning 2024-01-01 to 2024-01-06;
    # resample('D') fills the gap days (01-02, 01-03) with 0, giving 6 total periods.
    series = result["series"]
    assert len(series) == 6
    assert series.loc["2024-01-01"] == 1
    assert series.loc["2024-01-02"] == 0  # gap, correctly filled not dropped
    assert series.loc["2024-01-06"] == 6


def test_prepare_series_aggregates_duplicate_dates():
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "value": [10, 20, 30, 40, 50],
    })
    result = prepare_series(df, "date", "value", freq="D")
    assert result["series"].loc["2024-01-01"] == 30


def test_prepare_series_respects_freq_override():
    df = _monthly_trend_seasonal_df()
    result = prepare_series(df, "date", "value", freq="QE")
    assert result["freq"] == "QE"


def test_detect_trend_increasing():
    series = pd.Series(np.arange(20) * 10.0)
    trend = detect_trend(series)
    assert trend["direction"] == "increasing"
    assert trend["slope"] > 0


def test_detect_trend_decreasing():
    series = pd.Series(np.arange(20)[::-1] * 10.0)
    trend = detect_trend(series)
    assert trend["direction"] == "decreasing"
    assert trend["slope"] < 0


def test_detect_trend_stable():
    series = pd.Series([100.0] * 20)
    trend = detect_trend(series)
    assert trend["direction"] == "stable"


def test_detect_seasonality_finds_strong_yearly_pattern():
    df = _monthly_trend_seasonal_df(n=36, seasonal_amplitude=500, noise=5)
    prepared = prepare_series(df, "date", "value")
    result = detect_seasonality(prepared["series"], prepared["freq"])
    assert result["detected"] is True
    assert result["period"] == 12
    assert result["strength"] > 0.3


def test_detect_seasonality_none_for_flat_series():
    df = _daily_flat_df(n=30)
    prepared = prepare_series(df, "date", "value", freq="D")
    result = detect_seasonality(prepared["series"], prepared["freq"])
    assert result["detected"] is False


def test_detect_seasonality_insufficient_data_returns_not_detected():
    series = pd.Series([1.0, 2.0, 3.0, 4.0])
    result = detect_seasonality(series, "ME")
    assert result["detected"] is False


def test_generate_forecast_chooses_holt_winters_for_seasonal_data():
    df = _monthly_trend_seasonal_df(n=36, seasonal_amplitude=500, noise=5)
    prepared = prepare_series(df, "date", "value")
    result = generate_forecast(prepared["series"], prepared["freq"], periods=12)

    assert result["method"] == "holt_winters_seasonal"
    assert len(result["forecast"]) == 12
    assert result["trend"]["direction"] == "increasing"
    assert result["seasonality"]["detected"] is True


def test_generate_forecast_produces_widening_confidence_bands():
    df = _monthly_trend_seasonal_df(n=36)
    prepared = prepare_series(df, "date", "value")
    result = generate_forecast(prepared["series"], prepared["freq"], periods=12)

    first_width = result["forecast"][0]["upper"] - result["forecast"][0]["lower"]
    last_width = result["forecast"][-1]["upper"] - result["forecast"][-1]["lower"]
    assert last_width >= first_width


def test_generate_forecast_falls_back_for_short_series():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    series = pd.Series([10.0, 12.0, 11.0, 13.0, 14.0], index=dates)
    result = generate_forecast(series, "D", periods=3)

    assert result["method"] in ("linear_regression_fallback", "holt_linear_trend")
    assert len(result["forecast"]) == 3


def test_generate_forecast_rejects_invalid_periods():
    df = _monthly_trend_seasonal_df()
    prepared = prepare_series(df, "date", "value")
    with pytest.raises(ForecastError):
        generate_forecast(prepared["series"], prepared["freq"], periods=0)
    with pytest.raises(ForecastError):
        generate_forecast(prepared["series"], prepared["freq"], periods=500)


def test_generate_forecast_future_dates_continue_from_history():
    df = _monthly_trend_seasonal_df(n=24)
    prepared = prepare_series(df, "date", "value")
    result = generate_forecast(prepared["series"], prepared["freq"], periods=6)

    last_history_date = pd.Timestamp(result["history"][-1]["date"])
    first_forecast_date = pd.Timestamp(result["forecast"][0]["date"])
    assert first_forecast_date > last_history_date


def test_generate_forecast_history_matches_input_length():
    df = _monthly_trend_seasonal_df(n=24)
    prepared = prepare_series(df, "date", "value")
    result = generate_forecast(prepared["series"], prepared["freq"], periods=6)
    assert len(result["history"]) == 24
