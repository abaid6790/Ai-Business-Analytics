"""
Feature importance / explainability (spec section 14). Tries SHAP first
since it gives per-model, per-feature attribution that's more trustworthy
than a raw feature_importances_ / coef_ reading — but SHAP can be slow or
fail on some model/data combinations, so we fall back to the model's own
built-in importance when it does.

Both the background (reference) sample and the sample being explained are
capped in size — SHAP's runtime scales with both, and a 100-row cap keeps
this from becoming the slow part of training on a larger dataset (spec
section 31: 8GB RAM budget, no GPU).
"""

import numpy as np
import shap

MAX_BACKGROUND_ROWS = 50
MAX_EXPLAIN_ROWS = 100
TOP_FEATURES = 10


class ExplainabilityError(Exception):
    pass


def compute_feature_importance(fitted_pipeline, X_train_transformed, X_explain_transformed, feature_names, task_type) -> dict:
    estimator = fitted_pipeline.named_steps["estimator"]

    try:
        return _shap_importance(estimator, X_train_transformed, X_explain_transformed, feature_names, task_type)
    except Exception:
        return _builtin_importance(estimator, feature_names)


def _shap_importance(estimator, X_train, X_explain, feature_names, task_type) -> dict:
    background = _subsample(X_train, MAX_BACKGROUND_ROWS)
    explain_sample = _subsample(X_explain, MAX_EXPLAIN_ROWS)

    explainer = shap.Explainer(estimator, background)
    shap_values = explainer(explain_sample)

    values = shap_values.values
    if values.ndim == 3:
        # multi-class: average absolute importance across classes
        mean_abs = np.abs(values).mean(axis=(0, 2))
    else:
        mean_abs = np.abs(values).mean(axis=0)

    return _rank_features(mean_abs, feature_names, method="shap")


def _builtin_importance(estimator, feature_names) -> dict:
    if hasattr(estimator, "feature_importances_"):
        importances = np.asarray(estimator.feature_importances_)
        return _rank_features(importances, feature_names, method="model_builtin")

    if hasattr(estimator, "coef_"):
        coef = np.asarray(estimator.coef_)
        importances = np.abs(coef).mean(axis=0) if coef.ndim > 1 else np.abs(coef)
        return _rank_features(importances, feature_names, method="model_builtin")

    raise ExplainabilityError("This model type does not expose feature importances.")


def _rank_features(importances, feature_names, method) -> dict:
    if len(feature_names) != len(importances):
        feature_names = [f"feature_{i}" for i in range(len(importances))]

    clean_names = [_clean_feature_name(name) for name in feature_names]
    pairs = list(zip(clean_names, [round(float(v), 6) for v in importances]))
    pairs.sort(key=lambda p: p[1], reverse=True)
    top = pairs[:TOP_FEATURES]

    total = sum(v for _, v in pairs) or 1.0
    return {
        "method": method,
        "top_features": [
            {"feature": name, "importance": value, "importance_pct": round(value / total * 100, 2)}
            for name, value in top
        ],
    }


def _clean_feature_name(name: str) -> str:
    """ColumnTransformer prefixes output names with 'numeric__' /
    'categorical__' — strip those for a human-facing feature name while
    keeping the one-hot category suffix (e.g. 'categorical__region_east'
    -> 'region_east')."""
    for prefix in ("numeric__", "categorical__"):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _subsample(X, max_rows):
    if hasattr(X, "toarray"):
        X = X.toarray()
    X = np.asarray(X)
    if len(X) <= max_rows:
        return X
    rng = np.random.RandomState(42)
    idx = rng.choice(len(X), max_rows, replace=False)
    return X[idx]


def build_plain_language_explanation(feature_importance: dict, task_type: str, target_column: str) -> str:
    """Deterministic, template-based explanation — no AI call required, so
    this always works even with zero AI providers configured. Routes may
    optionally pass this through provider_manager.generate() for nicer
    prose; this text is already a correct, grounded fallback."""
    top = feature_importance["top_features"]
    if not top:
        return "No clear influential features were found for this model."

    top_names = [f["feature"] for f in top[:3]]
    verb = "predicting" if task_type == "classification" else "estimating"
    lead = f"The strongest factors {verb} {target_column} were " + ", ".join(top_names) + "."

    lines = [lead, ""]
    for f in top[:5]:
        lines.append(f"- {f['feature']}: {f['importance_pct']}% relative influence")

    return "\n".join(lines)
