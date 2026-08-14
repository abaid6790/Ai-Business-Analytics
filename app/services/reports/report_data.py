"""
Builds the full report data structure (spec section 16): dataset overview,
data quality, EDA, charts, AI insights, ML results, recommendations.

Every number here is either read directly off the Dataset row (computed at
upload/clean time) or recomputed live from the actual file via the same
services every other page uses (quality_scanner, eda, chart_builder) —
nothing in a report is invented or approximated beyond what those services
already do.
"""

import json

from app.services.analytics.eda import compute_descriptive_stats, compute_correlation_matrix
from app.services.analytics.quality_scanner import scan_quality
from app.services.analytics.chart_builder import build_chart_data, ChartBuildError
from app.services.reports.recommendations import build_recommendations

MAX_CHARTS_IN_REPORT = 4


def build_report_data(dataset, df, saved_charts, best_ml_model, latest_insight_message):
    overview = _build_overview(dataset)
    quality = scan_quality(df)
    eda_stats = compute_descriptive_stats(df)
    correlation = compute_correlation_matrix(df)

    charts = _render_chart_specs(df, saved_charts)
    ml_summary = _build_ml_summary(best_ml_model)
    insights_text, insight_facts = _build_insights(latest_insight_message)

    recommendations = build_recommendations(quality, ml_summary, insight_facts)

    return {
        "overview": overview,
        "quality": quality,
        "eda": eda_stats,
        "correlation": correlation,
        "charts": charts,
        "ml_summary": ml_summary,
        "insights_text": insights_text,
        "insight_facts": insight_facts,
        "recommendations": recommendations,
    }


def _build_overview(dataset):
    return {
        "dataset_name": dataset.name,
        "description": dataset.description,
        "original_filename": dataset.original_filename,
        "row_count": dataset.row_count,
        "column_count": dataset.column_count,
        "missing_values_count": dataset.missing_values_count,
        "duplicate_rows_count": dataset.duplicate_rows_count,
        "file_size_bytes": dataset.file_size_bytes,
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
        "is_cleaned_copy": dataset.is_cleaned_copy,
    }


def _render_chart_specs(df, saved_charts):
    charts = []
    for chart in saved_charts[:MAX_CHARTS_IN_REPORT]:
        try:
            spec = json.loads(chart.config_json)
            data = build_chart_data(df, spec)
            charts.append({"title": chart.title, "chart_type": chart.chart_type, "data": data})
        except (ChartBuildError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return charts


def _build_ml_summary(best_ml_model):
    if best_ml_model is None:
        return {"best_model": None}

    metrics = json.loads(best_ml_model.metrics_json) if best_ml_model.metrics_json else {}
    feature_importance = (
        json.loads(best_ml_model.feature_importance_json) if best_ml_model.feature_importance_json else None
    )

    return {
        "best_model": {
            "algorithm": best_ml_model.algorithm,
            "task_type": best_ml_model.task_type,
            "target_column": best_ml_model.target_column,
            "metrics": metrics,
            "top_features": (feature_importance or {}).get("top_features", [])[:5],
            "explanation_text": best_ml_model.explanation_text,
        }
    }


def _build_insights(latest_insight_message):
    if latest_insight_message is None:
        return None, []

    facts = []
    if latest_insight_message.computed_context_json:
        try:
            facts = json.loads(latest_insight_message.computed_context_json)
        except (ValueError, TypeError):
            facts = []

    return latest_insight_message.content, facts
