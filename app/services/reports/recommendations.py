"""
Generates plain business recommendations from already-computed facts
(quality issues, ML results, insight facts). Deterministic and
template-based — unlike the AI Analyst/Insights features (Phase 8), this
never calls an AI provider, so a report can always be generated even with
zero AI providers configured. Every recommendation traces directly back to
a specific computed number, never an invented one.
"""


def build_recommendations(quality: dict, ml_summary: dict, insight_facts: list) -> list:
    recommendations = []

    if quality:
        dup_count = quality.get("duplicates", {}).get("count", 0)
        if dup_count > 0:
            recommendations.append(
                f"Remove {dup_count} duplicate row(s) before further analysis — "
                "they can inflate totals and skew averages."
            )

        missing = quality.get("missing", {}).get("columns_with_missing", {})
        if missing:
            worst_col, worst_info = max(missing.items(), key=lambda kv: kv[1]["count"])
            recommendations.append(
                f"'{worst_col}' has {worst_info['percentage']}% missing values — "
                "consider imputing or investigating why this data is incomplete."
            )

        if quality.get("constant_columns"):
            cols = ", ".join(quality["constant_columns"])
            recommendations.append(f"Column(s) with only one distinct value ({cols}) add no predictive value and can be dropped.")

        if quality.get("outliers"):
            worst_col = max(quality["outliers"].items(), key=lambda kv: kv[1]["count"])
            recommendations.append(
                f"'{worst_col[0]}' has {worst_col[1]['count']} statistical outlier(s) — "
                "review these rows before using this column in models or KPIs."
            )

    if ml_summary and ml_summary.get("best_model"):
        best = ml_summary["best_model"]
        if best["task_type"] == "classification" and best["metrics"].get("accuracy", 1) < 0.7:
            recommendations.append(
                f"The best model ({best['algorithm']}) reached only "
                f"{best['metrics']['accuracy']*100:.1f}% accuracy — consider adding more features "
                "or collecting more training data before relying on it."
            )
        elif best["task_type"] == "regression" and best["metrics"].get("r2", 1) < 0.5:
            recommendations.append(
                f"The best model ({best['algorithm']}) explains only "
                f"{best['metrics']['r2']*100:.1f}% of the variance in the target — "
                "predictions from it should be treated as rough estimates."
            )
        else:
            score_label = "accuracy" if best["task_type"] == "classification" else "R\u00b2"
            score_value = best["metrics"].get("accuracy" if best["task_type"] == "classification" else "r2")
            recommendations.append(
                f"'{best['algorithm']}' is the strongest model trained so far "
                f"({score_label}: {score_value}) — it's ready to use for predictions on new data."
            )

    for fact in insight_facts or []:
        if fact.get("type") == "trend" and fact.get("percent_change") is not None:
            detail = fact.get("detail", "A tracked metric")
            direction = "growing" if fact["percent_change"] > 0 else "declining"
            recommendations.append(
                f"{detail} is {direction} ({fact['percent_change']}%) — "
                f"{'capitalize on this momentum' if fact['percent_change'] > 0 else 'investigate the cause before it compounds'}."
            )

    if not recommendations:
        recommendations.append("No significant data quality issues or risks were detected in this analysis.")

    return recommendations
