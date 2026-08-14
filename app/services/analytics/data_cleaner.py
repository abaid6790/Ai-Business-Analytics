"""
Applies user-selected cleaning actions to a dataframe copy. Every action is
a whitelisted, parameterized operation — never arbitrary code — matching
the "controlled execution" principle used throughout the AI layer too.
"""

import pandas as pd

IQR_MULTIPLIER = 1.5


class CleaningError(Exception):
    pass


def apply_cleaning_actions(df: pd.DataFrame, actions: list) -> tuple[pd.DataFrame, list]:
    """
    Returns (cleaned_df, applied_log). Never mutates the input dataframe —
    always works on a copy, so the caller's original stays untouched even
    if this function is called against an in-memory frame rather than a
    freshly re-read file.
    """
    working = df.copy(deep=True)
    log = []

    for action in actions:
        action_type = action.get("type")
        handler = _ACTION_HANDLERS.get(action_type)
        if handler is None:
            raise CleaningError(f"Unknown cleaning action: {action_type}")
        working, description = handler(working, action)
        log.append(description)

    return working, log


def _remove_duplicates(df, action):
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    return df, f"Removed {removed} duplicate row(s)."


def _drop_missing(df, action):
    column = action.get("column")
    before = len(df)
    if column:
        df = df.dropna(subset=[column])
        desc_col = f"column '{column}'"
    else:
        df = df.dropna()
        desc_col = "any column"
    removed = before - len(df)
    return df, f"Dropped {removed} row(s) with missing values in {desc_col}."


def _fill_missing(df, action):
    column = action.get("column")
    strategy = action.get("strategy")
    if column not in df.columns:
        raise CleaningError(f"Column '{column}' not found.")

    missing_before = int(df[column].isna().sum())

    if strategy == "mean":
        value = df[column].mean()
    elif strategy == "median":
        value = df[column].median()
    elif strategy == "mode":
        mode_vals = df[column].mode(dropna=True)
        value = mode_vals.iloc[0] if not mode_vals.empty else None
    elif strategy == "constant":
        value = action.get("value")
    elif strategy == "zero":
        value = 0
    else:
        raise CleaningError(f"Unknown fill strategy: {strategy}")

    df[column] = df[column].fillna(value)
    return df, f"Filled {missing_before} missing value(s) in '{column}' using strategy '{strategy}'."


def _convert_type(df, action):
    column = action.get("column")
    target_type = action.get("target_type")
    if column not in df.columns:
        raise CleaningError(f"Column '{column}' not found.")

    try:
        if target_type == "int":
            df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
        elif target_type == "float":
            df[column] = pd.to_numeric(df[column], errors="coerce")
        elif target_type == "string":
            df[column] = df[column].astype(str)
        elif target_type == "datetime":
            df[column] = pd.to_datetime(df[column], errors="coerce", format="mixed")
        elif target_type == "category":
            df[column] = df[column].astype("category")
        else:
            raise CleaningError(f"Unknown target type: {target_type}")
    except (ValueError, TypeError) as exc:
        raise CleaningError(f"Could not convert '{column}' to {target_type}: {exc}") from exc

    return df, f"Converted '{column}' to {target_type}."


def _drop_column(df, action):
    column = action.get("column")
    if column not in df.columns:
        raise CleaningError(f"Column '{column}' not found.")
    df = df.drop(columns=[column])
    return df, f"Dropped column '{column}'."


def _handle_outliers(df, action):
    column = action.get("column")
    method = action.get("method", "clip")
    if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
        raise CleaningError(f"Column '{column}' is not a numeric column.")

    series = df[column].dropna()
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - IQR_MULTIPLIER * iqr
    upper = q3 + IQR_MULTIPLIER * iqr

    if method == "clip":
        df[column] = df[column].clip(lower=lower, upper=upper)
        return df, f"Clipped outliers in '{column}' to [{lower:.2f}, {upper:.2f}]."
    elif method == "remove":
        before = len(df)
        df = df[(df[column].isna()) | ((df[column] >= lower) & (df[column] <= upper))]
        removed = before - len(df)
        return df, f"Removed {removed} outlier row(s) from '{column}'."
    else:
        raise CleaningError(f"Unknown outlier method: {method}")


_ACTION_HANDLERS = {
    "remove_duplicates": _remove_duplicates,
    "drop_missing": _drop_missing,
    "fill_missing": _fill_missing,
    "convert_type": _convert_type,
    "drop_column": _drop_column,
    "handle_outliers": _handle_outliers,
}
