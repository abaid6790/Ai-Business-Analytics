"""
Builds a Pipeline(ColumnTransformer(...), estimator) per spec section 12:
"Prevent data leakage using Scikit-learn Pipelines and ColumnTransformer."

All fitting (imputer statistics, scaler mean/std, one-hot categories)
happens only on the training fold — because it's wrapped in a Pipeline,
cross_val_score and the final train/test split both refit preprocessing
from scratch on each training subset, never peeking at test data.
"""

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

MAX_ONEHOT_CARDINALITY = 30


class FeatureSetupError(Exception):
    pass


def classify_features(df: pd.DataFrame, feature_columns: list) -> dict:
    numeric_features, categorical_features, dropped_high_cardinality = [], [], []

    for col in feature_columns:
        if pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_bool_dtype(df[col]):
            numeric_features.append(col)
        else:
            nunique = df[col].nunique(dropna=True)
            if nunique > MAX_ONEHOT_CARDINALITY:
                dropped_high_cardinality.append(col)
            else:
                categorical_features.append(col)

    return {
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "dropped_high_cardinality": dropped_high_cardinality,
    }


def build_preprocessor(numeric_features: list, categorical_features: list) -> ColumnTransformer:
    transformers = []

    if numeric_features:
        numeric_pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ])
        transformers.append(("numeric", numeric_pipeline, numeric_features))

    if categorical_features:
        categorical_pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ])
        transformers.append(("categorical", categorical_pipeline, categorical_features))

    if not transformers:
        raise FeatureSetupError("No usable feature columns after filtering.")

    return ColumnTransformer(transformers)


def build_pipeline(numeric_features: list, categorical_features: list, estimator) -> Pipeline:
    preprocessor = build_preprocessor(numeric_features, categorical_features)
    return Pipeline([
        ("preprocessor", preprocessor),
        ("estimator", estimator),
    ])


def get_output_feature_names(fitted_preprocessor: ColumnTransformer) -> list:
    """Feature names *after* one-hot expansion — needed to label SHAP/
    feature-importance results meaningfully."""
    try:
        return list(fitted_preprocessor.get_feature_names_out())
    except Exception:
        return []
