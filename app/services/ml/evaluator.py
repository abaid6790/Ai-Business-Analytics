"""
Evaluation metrics per spec section 13.
"""

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)


def evaluate_classification(y_true, y_pred, y_proba=None, labels=None) -> dict:
    labels = labels if labels is not None else sorted(set(y_true) | set(y_pred))
    average = "binary" if len(labels) == 2 else "weighted"

    metrics = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, average=average, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, average=average, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, average=average, zero_division=0)), 4),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "labels": [str(l) for l in labels],
    }

    if y_proba is not None:
        try:
            if len(labels) == 2:
                metrics["roc_auc"] = round(float(roc_auc_score(y_true, y_proba[:, 1])), 4)
            else:
                metrics["roc_auc"] = round(
                    float(roc_auc_score(y_true, y_proba, multi_class="ovr", average="weighted")), 4
                )
        except ValueError:
            metrics["roc_auc"] = None
    else:
        metrics["roc_auc"] = None

    return metrics


def evaluate_regression(y_true, y_pred) -> dict:
    mse = mean_squared_error(y_true, y_pred)
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "mse": round(float(mse), 4),
        "rmse": round(float(np.sqrt(mse)), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 4),
    }


def primary_metric(task_type: str, metrics: dict) -> float:
    """The single number used to rank models against each other."""
    if task_type == "classification":
        return metrics["accuracy"]
    return metrics["r2"]
