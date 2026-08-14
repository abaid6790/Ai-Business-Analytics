"""
Trains a single algorithm end to end: split -> cross-validate -> fit ->
evaluate -> explain. Called once per algorithm by the job runner, which
loops over the full algorithm set for a task type (spec section 12/13/14).
"""

import time

import numpy as np
from sklearn.model_selection import cross_val_score, train_test_split

from app.services.ml.evaluator import evaluate_classification, evaluate_regression
from app.services.ml.explainability import build_plain_language_explanation, compute_feature_importance
from app.services.ml.pipeline_builder import build_pipeline, get_output_feature_names

TEST_SIZE = 0.2
CV_FOLDS = 5
RANDOM_STATE = 42
MIN_ROWS_FOR_CV = 30  # below this, skip cross-validation (too few folds to be meaningful)


class TrainingError(Exception):
    pass


def train_single_model(X, y, numeric_features, categorical_features, estimator_factory,
                        task_type, target_column, algorithm_name):
    start = time.monotonic()

    stratify = y if task_type == "classification" and y.nunique() > 1 else None
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=stratify
        )
    except ValueError:
        # Stratification can fail if a class has too few members — retry without it.
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
        )

    pipeline = build_pipeline(numeric_features, categorical_features, estimator_factory())

    cv_scores = None
    if len(X_train) >= MIN_ROWS_FOR_CV:
        try:
            scoring = "accuracy" if task_type == "classification" else "r2"
            folds = min(CV_FOLDS, max(2, len(X_train) // 10))
            raw_scores = cross_val_score(pipeline, X_train, y_train, cv=folds, scoring=scoring)
            cv_scores = {
                "scoring": scoring,
                "folds": folds,
                "scores": [round(float(s), 4) for s in raw_scores],
                "mean": round(float(np.mean(raw_scores)), 4),
                "std": round(float(np.std(raw_scores)), 4),
            }
        except Exception:
            cv_scores = None  # CV is a nice-to-have; don't fail training over it

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    if task_type == "classification":
        y_proba = None
        if hasattr(pipeline.named_steps["estimator"], "predict_proba"):
            y_proba = pipeline.predict_proba(X_test)
        metrics = evaluate_classification(y_test, y_pred, y_proba, labels=sorted(y.unique()))
    else:
        metrics = evaluate_regression(y_test, y_pred)

    feature_names = get_output_feature_names(pipeline.named_steps["preprocessor"])
    X_train_transformed = pipeline.named_steps["preprocessor"].transform(X_train)
    X_test_transformed = pipeline.named_steps["preprocessor"].transform(X_test)

    try:
        importance = compute_feature_importance(
            pipeline, X_train_transformed, X_test_transformed, feature_names, task_type
        )
    except Exception:
        importance = {"method": "unavailable", "top_features": []}

    explanation = build_plain_language_explanation(importance, task_type, target_column)

    elapsed = time.monotonic() - start

    return {
        "algorithm": algorithm_name,
        "pipeline": pipeline,
        "metrics": metrics,
        "cv_scores": cv_scores,
        "feature_importance": importance,
        "explanation_text": explanation,
        "training_time_seconds": round(elapsed, 3),
    }
