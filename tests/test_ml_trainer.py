import numpy as np
import pandas as pd
import pytest

from app.services.ml.trainer import train_single_model
from app.services.ml.model_registry import classification_algorithms, regression_algorithms
from app.services.ml.explainability import compute_feature_importance, build_plain_language_explanation


def _classification_data(n=120):
    rng = np.random.RandomState(0)
    X = pd.DataFrame({
        "score": rng.normal(50, 10, n),
        "age": rng.randint(18, 65, n),
        "segment": rng.choice(["a", "b", "c"], n),
    })
    y = pd.Series((X["score"] > 50).astype(int), name="target")
    return X, y


def _regression_data(n=120):
    rng = np.random.RandomState(1)
    X = pd.DataFrame({
        "experience": rng.randint(0, 30, n),
        "age": rng.randint(20, 60, n),
        "department": rng.choice(["eng", "sales"], n),
    })
    y = pd.Series(30000 + X["experience"] * 1500 + rng.normal(0, 1000, n), name="salary")
    return X, y


# --- trainer -----------------------------------------------------------
def test_train_single_model_classification_produces_real_metrics():
    X, y = _classification_data()
    algo = classification_algorithms()["RandomForestClassifier"]

    result = train_single_model(X, y, ["score", "age"], ["segment"], algo, "classification", "target", "RandomForestClassifier")

    assert result["algorithm"] == "RandomForestClassifier"
    assert 0.0 <= result["metrics"]["accuracy"] <= 1.0
    assert result["metrics"]["accuracy"] > 0.7  # should learn something real from a clear signal
    assert result["cv_scores"] is not None
    assert result["training_time_seconds"] > 0
    assert "score" in [f["feature"] for f in result["feature_importance"]["top_features"]]


def test_train_single_model_regression_produces_real_metrics():
    X, y = _regression_data()
    algo = regression_algorithms()["LinearRegression"]

    result = train_single_model(X, y, ["experience", "age"], ["department"], algo, "regression", "salary", "LinearRegression")

    assert result["metrics"]["r2"] > 0.8  # salary was constructed almost linearly from experience
    assert "mae" in result["metrics"]
    assert "rmse" in result["metrics"]
    top_feature_names = [f["feature"] for f in result["feature_importance"]["top_features"]]
    assert "experience" in top_feature_names[:2]  # should be the dominant driver


def test_train_single_model_pipeline_is_fitted_and_usable():
    X, y = _classification_data()
    algo = classification_algorithms()["LogisticRegression"]
    result = train_single_model(X, y, ["score", "age"], ["segment"], algo, "classification", "target", "LogisticRegression")

    # The fitted pipeline should be directly usable for new predictions
    sample = X.iloc[[0]]
    prediction = result["pipeline"].predict(sample)
    assert prediction[0] in (0, 1)


def test_train_single_model_explanation_references_target():
    X, y = _regression_data()
    algo = regression_algorithms()["LinearRegression"]
    result = train_single_model(X, y, ["experience", "age"], ["department"], algo, "regression", "salary", "LinearRegression")
    assert "salary" in result["explanation_text"]


def test_train_single_model_handles_small_dataset_without_cv():
    rng = np.random.RandomState(0)
    n = 15  # below MIN_ROWS_FOR_CV after train/test split
    X = pd.DataFrame({"x": rng.normal(0, 1, n)})
    y = pd.Series(rng.randint(0, 2, n))
    algo = classification_algorithms()["LogisticRegression"]

    result = train_single_model(X, y, ["x"], [], algo, "classification", "y", "LogisticRegression")
    assert result["cv_scores"] is None  # too few rows — skipped, not crashed


# --- explainability ---------------------------------------------------------
def test_feature_importance_ranks_dominant_feature_first():
    rng = np.random.RandomState(0)
    X = rng.rand(100, 3)
    y = (X[:, 0] > 0.5).astype(int)  # only column 0 matters

    from sklearn.ensemble import RandomForestClassifier
    model = RandomForestClassifier(n_estimators=30, random_state=0)
    model.fit(X, y)

    class FakePipeline:
        named_steps = {"estimator": model}

    result = compute_feature_importance(FakePipeline(), X, X, ["a", "b", "c"], "classification")
    assert result["top_features"][0]["feature"] == "a"


def test_feature_importance_falls_back_when_shap_unavailable():
    from sklearn.ensemble import RandomForestClassifier

    rng = np.random.RandomState(0)
    X = rng.rand(50, 2)
    y = rng.randint(0, 2, 50)
    model = RandomForestClassifier(n_estimators=10, random_state=0)
    model.fit(X, y)

    class FakePipeline:
        named_steps = {"estimator": model}

    # Force the SHAP path to fail by passing malformed data, confirming the
    # builtin feature_importances_ fallback still produces a usable result.
    result = compute_feature_importance(FakePipeline(), "not valid data", "also not valid", ["a", "b"], "classification")
    assert result["method"] == "model_builtin"
    assert len(result["top_features"]) == 2


def test_build_plain_language_explanation_handles_empty_features():
    text = build_plain_language_explanation({"top_features": []}, "classification", "target")
    assert "No clear influential features" in text


def test_build_plain_language_explanation_lists_top_features():
    fi = {"top_features": [
        {"feature": "income", "importance": 1.0, "importance_pct": 80.0},
        {"feature": "age", "importance": 0.2, "importance_pct": 20.0},
    ]}
    text = build_plain_language_explanation(fi, "regression", "spending")
    assert "income" in text
    assert "spending" in text
    assert "80.0%" in text
