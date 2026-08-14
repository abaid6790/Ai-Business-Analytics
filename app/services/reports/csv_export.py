import csv


def export_csv(report_data: dict, path: str) -> None:
    rows = []

    overview = report_data["overview"]
    rows.append(("Section", "Metric", "Value"))
    for key, value in overview.items():
        rows.append(("Overview", key, value))

    quality = report_data["quality"]
    rows.append(("Data Quality", "total_missing_cells", quality["missing"]["total_missing_cells"]))
    rows.append(("Data Quality", "duplicate_rows", quality["duplicates"]["count"]))
    rows.append(("Data Quality", "constant_columns", ", ".join(quality["constant_columns"]) or "none"))
    rows.append(("Data Quality", "columns_with_outliers", len(quality["outliers"])))

    for col, stats in report_data["eda"]["numeric"].items():
        for stat_name, stat_value in stats.items():
            rows.append((f"EDA: {col}", stat_name, stat_value))

    ml = report_data["ml_summary"].get("best_model")
    if ml:
        rows.append(("ML", "best_algorithm", ml["algorithm"]))
        rows.append(("ML", "task_type", ml["task_type"]))
        for metric_name, metric_value in ml["metrics"].items():
            if metric_name not in ("confusion_matrix", "labels"):
                rows.append(("ML", metric_name, metric_value))

    for i, rec in enumerate(report_data["recommendations"], start=1):
        rows.append(("Recommendations", f"recommendation_{i}", rec))

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
