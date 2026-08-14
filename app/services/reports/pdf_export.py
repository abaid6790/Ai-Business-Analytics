"""
PDF export via reportlab (pure-Python, no system dependencies beyond the
pip package itself).
"""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.reports.chart_renderer import render_chart_png

PRIMARY_COLOR = colors.HexColor("#4f46e5")


def export_pdf(report_data, path, title):
    doc = SimpleDocTemplate(path, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = _build_styles()
    story = []

    _add_title_page(story, styles, title, report_data["overview"])
    story.append(PageBreak())

    _add_overview_section(story, styles, report_data["overview"])
    _add_quality_section(story, styles, report_data["quality"])
    _add_eda_section(story, styles, report_data["eda"])

    if report_data["charts"]:
        story.append(PageBreak())
        _add_charts_section(story, styles, report_data["charts"])

    if report_data["insights_text"]:
        story.append(PageBreak())
        _add_insights_section(story, styles, report_data["insights_text"])

    if report_data["ml_summary"].get("best_model"):
        story.append(PageBreak())
        _add_ml_section(story, styles, report_data["ml_summary"]["best_model"])

    story.append(PageBreak())
    _add_recommendations_section(story, styles, report_data["recommendations"])

    doc.build(story)


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", fontSize=24, leading=30, textColor=PRIMARY_COLOR, spaceAfter=12))
    styles.add(ParagraphStyle(name="SectionHeading", fontSize=16, leading=20, textColor=PRIMARY_COLOR, spaceBefore=16, spaceAfter=8))
    styles.add(ParagraphStyle(name="SubHeading", fontSize=12, leading=16, spaceBefore=10, spaceAfter=4, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="Body", fontSize=10, leading=14))
    return styles


def _add_title_page(story, styles, title, overview):
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph(title, styles["ReportTitle"]))
    story.append(Paragraph(f"Dataset: {overview['dataset_name']}", styles["Body"]))
    if overview.get("description"):
        story.append(Paragraph(overview["description"], styles["Body"]))
    story.append(Spacer(1, 0.3 * inch))
    row_count = overview["row_count"] or 0
    story.append(Paragraph(f"{row_count:,} rows &middot; {overview['column_count']} columns", styles["Body"]))


def _add_overview_section(story, styles, overview):
    story.append(Paragraph("Dataset Overview", styles["SectionHeading"]))
    rows = [
        ["Rows", f"{overview['row_count']:,}" if overview["row_count"] else "\u2014"],
        ["Columns", overview["column_count"] or "\u2014"],
        ["Missing values", f"{overview['missing_values_count']:,}" if overview["missing_values_count"] is not None else "\u2014"],
        ["Duplicate rows", overview["duplicate_rows_count"] if overview["duplicate_rows_count"] is not None else "\u2014"],
        ["File size", _format_bytes(overview["file_size_bytes"])],
        ["Source file", overview["original_filename"]],
    ]
    story.append(_styled_table(["Metric", "Value"], rows))


def _add_quality_section(story, styles, quality):
    story.append(Paragraph("Data Quality", styles["SectionHeading"]))

    summary_rows = [
        ["Total missing cells", quality["missing"]["total_missing_cells"]],
        ["Duplicate rows", quality["duplicates"]["count"]],
        ["Constant columns", ", ".join(quality["constant_columns"]) or "None"],
        ["High-cardinality columns", ", ".join(quality["high_cardinality_columns"]) or "None"],
    ]
    story.append(_styled_table(["Metric", "Value"], summary_rows))

    if quality["outliers"]:
        story.append(Paragraph("Columns with outliers", styles["SubHeading"]))
        outlier_rows = [[col, info["count"]] for col, info in quality["outliers"].items()]
        story.append(_styled_table(["Column", "Outlier count"], outlier_rows))


def _add_eda_section(story, styles, eda):
    story.append(Paragraph("Exploratory Data Analysis", styles["SectionHeading"]))

    if eda["numeric"]:
        story.append(Paragraph("Numeric columns", styles["SubHeading"]))
        header = ["Column", "Mean", "Median", "Std", "Min", "Max"]
        rows = [
            [col, s.get("mean"), s.get("median"), s.get("std"), s.get("min"), s.get("max")]
            for col, s in list(eda["numeric"].items())[:15]
        ]
        story.append(_styled_table(header, rows))

    if eda["categorical"]:
        story.append(Paragraph("Categorical columns", styles["SubHeading"]))
        header = ["Column", "Unique values", "Most common"]
        rows = []
        for col, s in list(eda["categorical"].items())[:15]:
            top = s.get("top_values", [{}])
            top_val = top[0].get("value") if top else "\u2014"
            rows.append([col, s.get("unique_count"), top_val])
        story.append(_styled_table(header, rows))


def _add_charts_section(story, styles, charts):
    story.append(Paragraph("Charts", styles["SectionHeading"]))
    for chart in charts:
        png_bytes = render_chart_png(chart["title"], chart["data"])
        story.append(Image(io.BytesIO(png_bytes), width=5.5 * inch, height=3.2 * inch))
        story.append(Spacer(1, 0.2 * inch))


def _add_insights_section(story, styles, insights_text):
    story.append(Paragraph("AI Insights", styles["SectionHeading"]))
    for line in insights_text.split("\n"):
        line = line.strip()
        if line:
            story.append(Paragraph(line, styles["Body"]))


def _add_ml_section(story, styles, best_model):
    story.append(Paragraph("Machine Learning Results", styles["SectionHeading"]))
    story.append(Paragraph(
        f"Best model: <b>{best_model['algorithm']}</b> ({best_model['task_type']}) "
        f"predicting <b>{best_model['target_column']}</b>",
        styles["Body"],
    ))

    metric_rows = [
        [k, v] for k, v in best_model["metrics"].items() if k not in ("confusion_matrix", "labels")
    ]
    story.append(_styled_table(["Metric", "Value"], metric_rows))

    if best_model.get("top_features"):
        story.append(Paragraph("Top influential features", styles["SubHeading"]))
        rows = [[f["feature"], f"{f['importance_pct']}%"] for f in best_model["top_features"]]
        story.append(_styled_table(["Feature", "Relative influence"], rows))

    if best_model.get("explanation_text"):
        story.append(Paragraph("Explanation", styles["SubHeading"]))
        for line in best_model["explanation_text"].split("\n"):
            if line.strip():
                story.append(Paragraph(line.strip(), styles["Body"]))


def _add_recommendations_section(story, styles, recommendations):
    story.append(Paragraph("Recommendations", styles["SectionHeading"]))
    items = [ListItem(Paragraph(rec, styles["Body"])) for rec in recommendations]
    story.append(ListFlowable(items, bulletType="bullet"))


def _styled_table(header, rows):
    data = [header] + [[_cell(v) for v in row] for row in rows]
    table = Table(data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f7fb")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _cell(value):
    if value is None:
        return "\u2014"
    if isinstance(value, float):
        return f"{value:,.4g}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _format_bytes(size):
    if not size:
        return "\u2014"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
