import pandas as pd
import pytest

from app.services.analytics.quality_scanner import scan_quality
from app.services.analytics.data_cleaner import apply_cleaning_actions, CleaningError


def _sample_df():
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5, 6],
        "category": ["a", "b", "a", "b", "a", "b"],
        "score": [10, 20, 10, 20, 10, 1000],  # 1000 is an outlier
        "notes": [None, "x", None, "y", None, "z"],
        "constant": [1, 1, 1, 1, 1, 1],
    })


def test_scan_quality_detects_missing_duplicates_constant_outliers():
    df = _sample_df()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # add a duplicate row

    result = scan_quality(df)

    assert result["duplicates"]["count"] == 1
    assert "notes" in result["missing"]["columns_with_missing"]
    assert result["missing"]["columns_with_missing"]["notes"]["count"] == 4
    assert "constant" in result["constant_columns"]
    assert "score" in result["outliers"]
    assert result["outliers"]["score"]["count"] >= 1


def test_scan_quality_dtype_mismatch_detection():
    df = pd.DataFrame({"amount": ["10", "20", "30", "N/A", "50"]})
    result = scan_quality(df)
    flagged_cols = [issue["column"] for issue in result["dtype_issues"]]
    assert "amount" in flagged_cols


def test_apply_remove_duplicates():
    df = _sample_df()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)

    cleaned, log = apply_cleaning_actions(df, [{"type": "remove_duplicates"}])
    assert len(cleaned) == len(df) - 1
    assert "Removed 1 duplicate" in log[0]


def test_apply_fill_missing_mean():
    df = pd.DataFrame({"x": [1.0, 2.0, None, 4.0]})
    cleaned, log = apply_cleaning_actions(
        df, [{"type": "fill_missing", "column": "x", "strategy": "mean"}]
    )
    assert cleaned["x"].isna().sum() == 0
    assert cleaned["x"].iloc[2] == pytest.approx((1.0 + 2.0 + 4.0) / 3)


def test_apply_drop_missing():
    df = pd.DataFrame({"x": [1, None, 3], "y": [1, 2, 3]})
    cleaned, log = apply_cleaning_actions(df, [{"type": "drop_missing", "column": "x"}])
    assert len(cleaned) == 2


def test_apply_convert_type():
    df = pd.DataFrame({"x": ["1", "2", "3"]})
    cleaned, log = apply_cleaning_actions(
        df, [{"type": "convert_type", "column": "x", "target_type": "int"}]
    )
    assert str(cleaned["x"].dtype) in ("Int64",)


def test_apply_drop_column():
    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    cleaned, log = apply_cleaning_actions(df, [{"type": "drop_column", "column": "y"}])
    assert "y" not in cleaned.columns


def test_apply_handle_outliers_clip():
    df = pd.DataFrame({"x": [10, 12, 11, 13, 1000]})
    cleaned, log = apply_cleaning_actions(
        df, [{"type": "handle_outliers", "column": "x", "method": "clip"}]
    )
    assert cleaned["x"].max() < 1000


def test_apply_handle_outliers_remove():
    df = pd.DataFrame({"x": [10, 12, 11, 13, 1000]})
    cleaned, log = apply_cleaning_actions(
        df, [{"type": "handle_outliers", "column": "x", "method": "remove"}]
    )
    assert 1000 not in cleaned["x"].values
    assert len(cleaned) == 4


def test_original_dataframe_never_mutated():
    df = pd.DataFrame({"x": [1, 1, 2]})
    original_copy = df.copy()
    apply_cleaning_actions(df, [{"type": "remove_duplicates"}])
    pd.testing.assert_frame_equal(df, original_copy)


def test_unknown_action_raises():
    df = pd.DataFrame({"x": [1, 2]})
    with pytest.raises(CleaningError):
        apply_cleaning_actions(df, [{"type": "nonexistent_action"}])


def test_convert_type_missing_column_raises():
    df = pd.DataFrame({"x": [1, 2]})
    with pytest.raises(CleaningError):
        apply_cleaning_actions(df, [{"type": "convert_type", "column": "missing", "target_type": "int"}])
