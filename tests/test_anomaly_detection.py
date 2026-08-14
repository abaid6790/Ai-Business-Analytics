import numpy as np
import pandas as pd
import pytest

from app.services.analytics.anomaly_detection import (
    AnomalyDetectionError,
    detect_anomalies,
)


def _df_with_obvious_outliers():
    # 9 normal values clustered around 10-13, one wildly different (1000)
    return pd.DataFrame({
        "amount": [10, 11, 12, 13, 10, 11, 12, 13, 10, 1000],
        "region": ["a"] * 10,
    })


def _df_multivariate():
    rng = np.random.RandomState(42)
    x = rng.normal(50, 5, 100)
    y = rng.normal(50, 5, 100)
    # inject one clear multivariate anomaly: normal-looking individually,
    # but the combination (high x, low y) is unusual
    x = np.append(x, 65)
    y = np.append(y, 20)
    return pd.DataFrame({"x": x, "y": y})


# --- Validation --------------------------------------------------------
def test_requires_at_least_one_column():
    df = _df_with_obvious_outliers()
    with pytest.raises(AnomalyDetectionError):
        detect_anomalies(df, "iqr", [])


def test_rejects_unknown_column():
    df = _df_with_obvious_outliers()
    with pytest.raises(AnomalyDetectionError):
        detect_anomalies(df, "iqr", ["nonexistent"])


def test_rejects_non_numeric_column():
    df = _df_with_obvious_outliers()
    with pytest.raises(AnomalyDetectionError):
        detect_anomalies(df, "iqr", ["region"])


def test_rejects_unknown_method():
    df = _df_with_obvious_outliers()
    with pytest.raises(AnomalyDetectionError):
        detect_anomalies(df, "not_a_method", ["amount"])


def test_rejects_insufficient_data():
    df = pd.DataFrame({"x": [1, 2]})
    with pytest.raises(AnomalyDetectionError):
        detect_anomalies(df, "iqr", ["x"])


# --- IQR -----------------------------------------------------------------
def test_iqr_detects_obvious_outlier():
    df = _df_with_obvious_outliers()
    result = detect_anomalies(df, "iqr", ["amount"])

    assert result["method"] == "iqr"
    assert result["anomaly_count"] >= 1
    flagged_indices = [a["row_index"] for a in result["anomalies"]]
    assert 9 in flagged_indices  # the row with value 1000


def test_iqr_result_includes_bounds():
    df = _df_with_obvious_outliers()
    result = detect_anomalies(df, "iqr", ["amount"])
    assert "amount" in result["bounds"]
    assert "lower" in result["bounds"]["amount"]
    assert "upper" in result["bounds"]["amount"]


def test_iqr_anomaly_row_includes_full_row_data():
    df = _df_with_obvious_outliers()
    result = detect_anomalies(df, "iqr", ["amount"])
    top = result["anomalies"][0]
    assert "amount" in top["row"]
    assert "region" in top["row"]  # full row, not just the analyzed column


def test_iqr_no_anomalies_in_uniform_data():
    df = pd.DataFrame({"x": [10, 10, 10, 10, 10, 10]})
    result = detect_anomalies(df, "iqr", ["x"])
    assert result["anomaly_count"] == 0


# --- Z-score ---------------------------------------------------------------
def test_zscore_detects_outlier_with_lower_threshold():
    df = _df_with_obvious_outliers()
    result = detect_anomalies(df, "zscore", ["amount"], threshold=1.5)
    assert result["anomaly_count"] >= 1
    assert result["threshold"] == 1.5


def test_zscore_respects_custom_threshold():
    df = _df_with_obvious_outliers()
    strict = detect_anomalies(df, "zscore", ["amount"], threshold=10.0)
    lenient = detect_anomalies(df, "zscore", ["amount"], threshold=0.5)
    assert strict["anomaly_count"] <= lenient["anomaly_count"]


# --- Isolation Forest -------------------------------------------------------
def test_isolation_forest_detects_multivariate_anomaly():
    df = _df_multivariate()
    result = detect_anomalies(df, "isolation_forest", ["x", "y"], contamination=0.05)

    assert result["method"] == "isolation_forest"
    assert result["anomaly_count"] >= 1
    flagged_indices = [a["row_index"] for a in result["anomalies"]]
    assert 100 in flagged_indices  # the injected anomaly is the last row


def test_isolation_forest_contamination_affects_count():
    df = _df_multivariate()
    low = detect_anomalies(df, "isolation_forest", ["x", "y"], contamination=0.01)
    high = detect_anomalies(df, "isolation_forest", ["x", "y"], contamination=0.3)
    assert low["anomaly_count"] <= high["anomaly_count"]


def test_isolation_forest_reproducible_with_fixed_seed():
    df = _df_multivariate()
    r1 = detect_anomalies(df, "isolation_forest", ["x", "y"])
    r2 = detect_anomalies(df, "isolation_forest", ["x", "y"])
    assert r1["anomaly_count"] == r2["anomaly_count"]


# --- Truncation & general shape ---------------------------------------------
def test_result_capped_at_max_anomalies_returned():
    # Outliers must stay a minority of the data — if they're too large a
    # share, IQR's own quartiles shift to include them as "normal" range.
    # 2000 normal values + 250 outliers (~11%) keeps them a clear minority
    # while still exceeding the MAX_ANOMALIES_RETURNED cap of 200.
    normal = list(range(10, 20)) * 200  # 2000 normal-ish values
    outliers = [5000] * 250
    df = pd.DataFrame({"x": normal + outliers})

    result = detect_anomalies(df, "iqr", ["x"])
    assert len(result["anomalies"]) <= 200
    assert result["truncated"] is True
    assert result["anomaly_count"] > len(result["anomalies"])


def test_rows_with_missing_values_excluded_from_analysis():
    df = pd.DataFrame({"x": [10, 11, 12, None, 13, 1000]})
    result = detect_anomalies(df, "iqr", ["x"])
    assert result["row_count"] == 5  # the None row dropped before analysis
