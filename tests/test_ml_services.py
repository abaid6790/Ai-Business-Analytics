import pandas as pd
import pytest

from app.services.ml.task_detector import detect_task_type, TaskDetectionError
from app.services.ml.pipeline_builder import (
    classify_features,
    build_pipeline,
    build_preprocessor,
    get_output_feature_names,
    FeatureSetupError,
)
from app.services.ml.evaluator import evaluate_classification, evaluate_regression, primary_metric


# --- task_detector -----------------------------------------------------
def test_detects_regression_for_continuous_numeric():
    series = pd.Series([float(i) * 1.37 for i in range(100)])
    assert detect_task_type(series) == "regression"


def test_detects_classification_for_binary_numeric():
    series = pd.Series([0, 1, 0, 1, 1, 0] * 10)
    assert detect_task_type(series) == "classification"


def test_detects_classification_for_text_labels():
    series = pd.Series(["yes", "no", "yes", "no"] * 10)
    assert detect_task_type(series) == "classification"


def test_detects_classification_for_boolean():
    series = pd.Series([True, False, True, False] * 10)
    assert detect_task_type(series) == "classification"


def test_detects_classification_for_low_cardinality_numeric():
    # ratings 1-5 — numeric but clearly categorical in intent
    series = pd.Series([1, 2, 3, 4, 5] * 20)
    assert detect_task_type(series) == "classification"


def test_raises_on_all_missing_target():
    series = pd.Series([None, None, None])
    with pytest.raises(TaskDetectionError):
        detect_task_type(series)


# --- pipeline_builder ----------------------------------------------------
def test_classify_features_splits_numeric_and_categorical():
    df = pd.DataFrame({
        "age": [1, 2, 3], "income": [10.0, 20.0, 30.0], "region": ["a", "b", "c"],
    })
    result = classify_features(df, ["age", "income", "region"])
    assert set(result["numeric_features"]) == {"age", "income"}
    assert result["categorical_features"] == ["region"]


def test_classify_features_drops_high_cardinality_categorical():
    df = pd.DataFrame({"id_col": [f"id_{i}" for i in range(100)]})
    result = classify_features(df, ["id_col"])
    assert "id_col" in result["dropped_high_cardinality"]
    assert "id_col" not in result["categorical_features"]


def test_build_preprocessor_requires_at_least_one_feature_type():
    with pytest.raises(FeatureSetupError):
        build_preprocessor([], [])


def test_build_pipeline_and_output_feature_names():
    df = pd.DataFrame({
        "age": [20, 30, 40, 50], "region": ["a", "b", "a", "b"], "target": [0, 1, 0, 1],
    })
    from sklearn.linear_model import LogisticRegression

    pipeline = build_pipeline(["age"], ["region"], LogisticRegression())
    pipeline.fit(df[["age", "region"]], df["target"])

    names = get_output_feature_names(pipeline.named_steps["preprocessor"])
    assert any("age" in n for n in names)
    assert any("region" in n for n in names)


# --- evaluator -------------------------------------------------------------
def test_evaluate_classification_binary():
    y_true = [0, 0, 1, 1, 1]
    y_pred = [0, 0, 1, 1, 0]
    metrics = evaluate_classification(y_true, y_pred)
    assert metrics["accuracy"] == pytest.approx(0.8)
    assert len(metrics["confusion_matrix"]) == 2


def test_evaluate_classification_perfect_predictions():
    y_true = [0, 1, 0, 1]
    y_pred = [0, 1, 0, 1]
    metrics = evaluate_classification(y_true, y_pred)
    assert metrics["accuracy"] == 1.0
    assert metrics["f1"] == 1.0


def test_evaluate_regression_metrics():
    y_true = [10, 20, 30, 40]
    y_pred = [12, 18, 33, 37]
    metrics = evaluate_regression(y_true, y_pred)
    assert metrics["mae"] > 0
    assert metrics["rmse"] >= metrics["mae"]  # RMSE >= MAE always holds
    assert "r2" in metrics


def test_evaluate_regression_perfect_predictions():
    y_true = [1, 2, 3, 4]
    y_pred = [1, 2, 3, 4]
    metrics = evaluate_regression(y_true, y_pred)
    assert metrics["r2"] == 1.0
    assert metrics["mae"] == 0.0


def test_primary_metric_classification_uses_accuracy():
    assert primary_metric("classification", {"accuracy": 0.9, "r2": 0.1}) == 0.9


def test_primary_metric_regression_uses_r2():
    assert primary_metric("regression", {"accuracy": 0.1, "r2": 0.85}) == 0.85
