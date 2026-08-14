"""
The fixed set of algorithms trained and compared per task type (spec
section 12). Kept as factory functions (not shared instances) since each
gets fit fresh inside its own Pipeline.
"""

from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier, XGBRegressor

RANDOM_STATE = 42


def classification_algorithms() -> dict:
    return {
        "LogisticRegression": lambda: LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
        "DecisionTreeClassifier": lambda: DecisionTreeClassifier(random_state=RANDOM_STATE),
        "RandomForestClassifier": lambda: RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE),
        "GradientBoostingClassifier": lambda: GradientBoostingClassifier(random_state=RANDOM_STATE),
        "XGBClassifier": lambda: XGBClassifier(random_state=RANDOM_STATE, eval_metric="logloss"),
    }


def regression_algorithms() -> dict:
    return {
        "LinearRegression": lambda: LinearRegression(),
        "RandomForestRegressor": lambda: RandomForestRegressor(n_estimators=200, random_state=RANDOM_STATE),
        "GradientBoostingRegressor": lambda: GradientBoostingRegressor(random_state=RANDOM_STATE),
        "XGBRegressor": lambda: XGBRegressor(random_state=RANDOM_STATE),
    }


def algorithms_for_task(task_type: str) -> dict:
    if task_type == "classification":
        return classification_algorithms()
    if task_type == "regression":
        return regression_algorithms()
    raise ValueError(f"Unknown task type: {task_type!r}")
