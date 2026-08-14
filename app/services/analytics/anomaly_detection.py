"""
Anomaly detection across three methods (spec section 11):
  - IQR: univariate, per-column bounds — same statistical basis as the
    quality scanner's outlier check, but here we return row-level detail
    (which exact rows, with a comparable score) rather than just a count.
  - Z-score: univariate, flags values far from the column mean in units
    of standard deviation.
  - Isolation Forest: multivariate — can catch a row that's anomalous as a
    *combination* of columns even when no single column looks unusual.

All three return the same shape so the UI doesn't need to know which
method produced the result.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

IQR_MULTIPLIER = 1.5
DEFAULT_ZSCORE_THRESHOLD = 3.0
DEFAULT_CONTAMINATION = 0.05
ISOLATION_FOREST_RANDOM_STATE = 42
MAX_ANOMALIES_RETURNED = 200


class AnomalyDetectionError(Exception):
    pass


def detect_anomalies(df: pd.DataFrame, method: str, columns: list, **params) -> dict:
    if not columns:
        raise AnomalyDetectionError("Select at least one numeric column.")

    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise AnomalyDetectionError(f"Column(s) not found: {', '.join(missing)}")

    non_numeric = [c for c in columns if not pd.api.types.is_numeric_dtype(df[c])]
    if non_numeric:
        raise AnomalyDetectionError(f"Column(s) are not numeric: {', '.join(non_numeric)}")

    subset = df[columns].dropna()
    if len(subset) < 4:
        raise AnomalyDetectionError("Not enough non-missing numeric data to analyze.")

    if method == "iqr":
        return _detect_iqr(df, subset, columns)
    if method == "zscore":
        threshold = float(params.get("threshold", DEFAULT_ZSCORE_THRESHOLD))
        return _detect_zscore(df, subset, columns, threshold)
    if method == "isolation_forest":
        contamination = float(params.get("contamination", DEFAULT_CONTAMINATION))
        return _detect_isolation_forest(df, subset, columns, contamination)

    raise AnomalyDetectionError(f"Unknown method: {method!r}")


def _finalize(df, columns, method, scores, is_anomaly, extra_meta=None):
    row_count = len(scores)
    anomaly_mask = is_anomaly
    anomaly_indices = scores.index[anomaly_mask]

    ranked = scores[anomaly_mask].sort_values(ascending=False)
    top_indices = ranked.index[:MAX_ANOMALIES_RETURNED]

    anomalies = []
    for idx in top_indices:
        row = df.loc[idx]
        row_data = {col: _safe_value(row[col]) for col in df.columns}
        anomalies.append({
            "row_index": int(idx),
            "score": round(float(ranked.loc[idx]), 4),
            "row": row_data,
        })

    result = {
        "method": method,
        "columns": columns,
        "row_count": int(row_count),
        "anomaly_count": int(anomaly_mask.sum()),
        "anomalies": anomalies,
        "truncated": int(anomaly_mask.sum()) > MAX_ANOMALIES_RETURNED,
    }
    if extra_meta:
        result.update(extra_meta)
    return result


def _detect_iqr(df, subset, columns):
    bounds = {}
    col_scores = pd.DataFrame(index=subset.index)

    for col in columns:
        q1, q3 = subset[col].quantile(0.25), subset[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - IQR_MULTIPLIER * iqr
        upper = q3 + IQR_MULTIPLIER * iqr
        bounds[col] = {"lower": round(float(lower), 4), "upper": round(float(upper), 4)}

        if iqr == 0:
            col_scores[col] = 0.0
            continue

        below = (lower - subset[col]).clip(lower=0) / iqr
        above = (subset[col] - upper).clip(lower=0) / iqr
        col_scores[col] = below.combine(above, max)

    scores = col_scores.max(axis=1)
    is_anomaly = scores > 0

    return _finalize(df, columns, "iqr", scores, is_anomaly, extra_meta={"bounds": bounds})


def _detect_zscore(df, subset, columns, threshold):
    means = subset[columns].mean()
    stds = subset[columns].std().replace(0, np.nan)

    z = (subset[columns] - means) / stds
    z = z.fillna(0)
    scores = z.abs().max(axis=1)
    is_anomaly = scores > threshold

    return _finalize(
        df, columns, "zscore", scores, is_anomaly,
        extra_meta={"threshold": threshold},
    )


def _detect_isolation_forest(df, subset, columns, contamination):
    contamination = min(max(contamination, 0.001), 0.5)

    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=ISOLATION_FOREST_RANDOM_STATE,
    )
    model.fit(subset[columns].values)

    # decision_function: lower (more negative) = more anomalous.
    # Flip sign so higher score = more anomalous, consistent with IQR/z-score.
    raw_scores = -model.decision_function(subset[columns].values)
    predictions = model.predict(subset[columns].values)  # -1 = anomaly, 1 = normal

    scores = pd.Series(raw_scores, index=subset.index)
    is_anomaly = pd.Series(predictions == -1, index=subset.index)

    return _finalize(
        df, columns, "isolation_forest", scores, is_anomaly,
        extra_meta={"contamination": contamination},
    )


def _safe_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return round(float(value), 6)
    return value
