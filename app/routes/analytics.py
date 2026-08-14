import json

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Dataset, Chart
from app.forms.chart_forms import SaveChartForm
from app.utils.ownership import get_owned_or_404, owner_scoped_query
from app.utils.activity import log_activity
from app.services.analytics.dataset_processor import read_full_dataframe, DatasetProfilingError
from app.services.analytics.eda import compute_descriptive_stats, compute_correlation_matrix
from app.services.analytics.chart_suggestions import suggest_charts
from app.services.analytics.chart_builder import build_chart_data, ChartBuildError

analytics_bp = Blueprint("analytics", __name__, template_folder="../templates/analytics")


def _load_dataframe_or_redirect(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
    except DatasetProfilingError:
        return dataset, None
    return dataset, df


# ---------------------------------------------------------------------------
# Automatic EDA
# ---------------------------------------------------------------------------
@analytics_bp.route("/<int:dataset_id>/eda")
@login_required
def eda(dataset_id):
    dataset, df = _load_dataframe_or_redirect(dataset_id)
    if df is None:
        flash("Could not analyze this dataset's file.", "danger")
        return redirect(url_for("datasets.detail", dataset_id=dataset_id))

    return render_template("analytics/eda.html", dataset=dataset)


@analytics_bp.route("/<int:dataset_id>/eda/data")
@login_required
def eda_data(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
    except DatasetProfilingError as exc:
        return jsonify({"error": str(exc)}), 400

    stats = compute_descriptive_stats(df)
    correlation = compute_correlation_matrix(df)
    suggestions = suggest_charts(stats)

    charts = []
    for spec in suggestions:
        try:
            chart_data = build_chart_data(df, spec)
            charts.append({**spec, "data": chart_data})
        except ChartBuildError:
            continue  # skip suggestions that don't pan out (e.g. empty column)

    return jsonify({"stats": stats, "correlation": correlation, "charts": charts})


# ---------------------------------------------------------------------------
# Interactive chart builder
# ---------------------------------------------------------------------------
@analytics_bp.route("/<int:dataset_id>/charts/builder")
@login_required
def chart_builder(dataset_id):
    dataset, df = _load_dataframe_or_redirect(dataset_id)
    if df is None:
        flash("Could not analyze this dataset's file.", "danger")
        return redirect(url_for("datasets.detail", dataset_id=dataset_id))

    columns = list(df.columns.astype(str))
    numeric_columns = [c for c in columns if str(df[c].dtype).startswith(("int", "float"))]
    form = SaveChartForm()

    return render_template(
        "analytics/chart_builder.html",
        dataset=dataset,
        columns=columns,
        numeric_columns=numeric_columns,
        form=form,
    )


@analytics_bp.route("/<int:dataset_id>/charts/preview", methods=["POST"])
@login_required
def chart_preview(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
    except DatasetProfilingError as exc:
        return jsonify({"error": str(exc)}), 400

    spec = request.get_json(force=True, silent=True) or {}
    try:
        chart_data = build_chart_data(df, spec)
    except ChartBuildError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"data": chart_data})


@analytics_bp.route("/<int:dataset_id>/charts", methods=["POST"])
@login_required
def save_chart(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    form = SaveChartForm()

    if not form.validate_on_submit():
        for field_name, errors in form.errors.items():
            for error in errors:
                flash(f"{field_name}: {error}", "danger")
        return redirect(url_for("analytics.chart_builder", dataset_id=dataset_id))

    try:
        json.loads(form.config_json.data)
    except (TypeError, ValueError):
        flash("Invalid chart configuration.", "danger")
        return redirect(url_for("analytics.chart_builder", dataset_id=dataset_id))

    chart = Chart(
        user_id=current_user.id,
        dataset_id=dataset.id,
        title=form.title.data.strip(),
        chart_type=form.chart_type.data,
        config_json=form.config_json.data,
    )
    db.session.add(chart)
    db.session.commit()

    log_activity(current_user.id, "chart_saved", f"chart_id={chart.id} dataset_id={dataset.id}")
    flash("Chart saved.", "success")
    return redirect(url_for("analytics.chart_view", chart_id=chart.id))


@analytics_bp.route("/charts/list/<int:dataset_id>")
@login_required
def chart_list(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    page = request.args.get("page", 1, type=int)
    pagination = (
        owner_scoped_query(Chart)
        .filter_by(dataset_id=dataset.id)
        .order_by(Chart.created_at.desc())
        .paginate(page=page, per_page=24, error_out=False)
    )
    return render_template("analytics/chart_list.html", dataset=dataset, pagination=pagination)


@analytics_bp.route("/charts/<int:chart_id>")
@login_required
def chart_view(chart_id):
    chart = get_owned_or_404(Chart, chart_id)
    dataset = get_owned_or_404(Dataset, chart.dataset_id)

    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
        spec = json.loads(chart.config_json)
        chart_data = build_chart_data(df, spec)
    except (DatasetProfilingError, ChartBuildError, json.JSONDecodeError) as exc:
        flash(f"Could not render this chart: {exc}", "danger")
        chart_data = {"labels": [], "datasets": []}

    return render_template("analytics/chart_view.html", chart=chart, dataset=dataset, chart_data=chart_data)


@analytics_bp.route("/charts/<int:chart_id>/delete", methods=["POST"])
@login_required
def chart_delete(chart_id):
    chart = get_owned_or_404(Chart, chart_id)
    dataset_id = chart.dataset_id
    db.session.delete(chart)
    db.session.commit()
    log_activity(current_user.id, "chart_deleted", f"chart_id={chart_id}")
    flash("Chart deleted.", "info")
    return redirect(url_for("analytics.chart_list", dataset_id=dataset_id))
