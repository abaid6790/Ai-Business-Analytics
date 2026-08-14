import os
import uuid

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Dataset, Chart, MLModel, AIConversation, Report
from app.utils.ownership import get_owned_or_404, owner_scoped_query
from app.utils.activity import log_activity
from app.services.analytics.dataset_processor import read_full_dataframe, DatasetProfilingError
from app.services.reports.report_data import build_report_data
from app.services.reports.pdf_export import export_pdf
from app.services.reports.excel_export import export_excel
from app.services.reports.csv_export import export_csv
from app.services.reports.json_export import export_json

reports_bp = Blueprint("reports", __name__, template_folder="../templates/reports")

EXPORTERS = {
    "pdf": lambda data, path, title: export_pdf(data, path, title),
    "xlsx": lambda data, path, title: export_excel(data, path),
    "csv": lambda data, path, title: export_csv(data, path),
    "json": lambda data, path, title: export_json(data, path),
}


@reports_bp.route("/")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    pagination = owner_scoped_query(Report).order_by(Report.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("reports/index.html", pagination=pagination)


@reports_bp.route("/build/<int:dataset_id>")
@login_required
def builder(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)

    chart_count = owner_scoped_query(Chart).filter_by(dataset_id=dataset.id).count()
    best_model = (
        owner_scoped_query(MLModel)
        .filter_by(dataset_id=dataset.id, is_best_model=True, status="completed")
        .first()
    )
    latest_insights = (
        owner_scoped_query(AIConversation)
        .filter(AIConversation.dataset_id == dataset.id, AIConversation.title.like("Automatic insights:%"))
        .order_by(AIConversation.updated_at.desc())
        .first()
    )

    return render_template(
        "reports/builder.html",
        dataset=dataset,
        chart_count=chart_count,
        best_model=best_model,
        has_insights=latest_insights is not None,
    )


@reports_bp.route("/build/<int:dataset_id>", methods=["POST"])
@login_required
def generate(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)

    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
    except DatasetProfilingError as exc:
        flash(f"Could not read dataset: {exc}", "danger")
        return redirect(url_for("reports.builder", dataset_id=dataset.id))

    fmt = request.form.get("format", "pdf")
    if fmt not in EXPORTERS:
        flash("Unsupported export format.", "danger")
        return redirect(url_for("reports.builder", dataset_id=dataset.id))

    title = request.form.get("title", "").strip() or f"{dataset.name} Report"

    saved_charts = owner_scoped_query(Chart).filter_by(dataset_id=dataset.id).order_by(Chart.created_at.desc()).all()
    best_model = (
        owner_scoped_query(MLModel)
        .filter_by(dataset_id=dataset.id, is_best_model=True, status="completed")
        .first()
    )
    latest_insight_conv = (
        owner_scoped_query(AIConversation)
        .filter(AIConversation.dataset_id == dataset.id, AIConversation.title.like("Automatic insights:%"))
        .order_by(AIConversation.updated_at.desc())
        .first()
    )
    latest_insight_message = latest_insight_conv.messages.first() if latest_insight_conv else None

    report_data = build_report_data(dataset, df, saved_charts, best_model, latest_insight_message)

    reports_dir = os.path.join(current_app.config["REPORTS_FOLDER"], str(current_user.id))
    os.makedirs(reports_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{fmt}"
    file_path = os.path.join(reports_dir, filename)

    try:
        EXPORTERS[fmt](report_data, file_path, title)
    except Exception as exc:
        current_app.logger.exception("Report generation failed")
        flash(f"Report generation failed: {exc}", "danger")
        return redirect(url_for("reports.builder", dataset_id=dataset.id))

    report = Report(
        user_id=current_user.id,
        project_id=dataset.project_id,
        title=title,
        format=fmt,
        file_path=file_path,
    )
    db.session.add(report)
    db.session.commit()

    log_activity(current_user.id, "report_generated", f"dataset_id={dataset.id} format={fmt} report_id={report.id}")
    flash("Report generated.", "success")
    return redirect(url_for("reports.index"))


@reports_bp.route("/<int:report_id>/download")
@login_required
def download(report_id):
    report = get_owned_or_404(Report, report_id)
    if not os.path.isfile(report.file_path):
        flash("Report file is missing.", "danger")
        return redirect(url_for("reports.index"))

    from werkzeug.utils import secure_filename

    safe_title = secure_filename(report.title) or "report"
    download_name = f"{safe_title}.{report.format}"
    return send_file(report.file_path, as_attachment=True, download_name=download_name)


@reports_bp.route("/<int:report_id>/delete", methods=["POST"])
@login_required
def delete(report_id):
    report = get_owned_or_404(Report, report_id)
    if report.file_path and os.path.isfile(report.file_path):
        os.remove(report.file_path)
    db.session.delete(report)
    db.session.commit()
    flash("Report deleted.", "info")
    return redirect(url_for("reports.index"))
