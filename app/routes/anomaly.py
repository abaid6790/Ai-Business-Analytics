from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from app.models import Dataset
from app.utils.ownership import get_owned_or_404
from app.utils.activity import log_activity
from app.services.analytics.dataset_processor import read_full_dataframe, DatasetProfilingError
from app.services.analytics.anomaly_detection import detect_anomalies, AnomalyDetectionError

anomaly_bp = Blueprint("anomaly", __name__, template_folder="../templates/anomaly")


@anomaly_bp.route("/<int:dataset_id>")
@login_required
def index(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
    except DatasetProfilingError as exc:
        flash(f"Could not analyze this dataset: {exc}", "danger")
        return redirect(url_for("datasets.detail", dataset_id=dataset.id))

    numeric_columns = [c for c in df.columns if str(df[c].dtype).startswith(("int", "float"))]

    return render_template("anomaly/index.html", dataset=dataset, numeric_columns=numeric_columns)


@anomaly_bp.route("/<int:dataset_id>/detect", methods=["POST"])
@login_required
def detect(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
    except DatasetProfilingError as exc:
        return jsonify({"error": str(exc)}), 400

    body = request.get_json(force=True, silent=True) or {}
    method = body.get("method", "iqr")
    columns = body.get("columns") or []
    params = {}
    if "threshold" in body:
        params["threshold"] = body["threshold"]
    if "contamination" in body:
        params["contamination"] = body["contamination"]

    try:
        result = detect_anomalies(df, method, columns, **params)
    except AnomalyDetectionError as exc:
        return jsonify({"error": str(exc)}), 400

    log_activity(
        current_user.id, "anomaly_detection_run",
        f"dataset_id={dataset.id} method={method} columns={columns} anomalies={result['anomaly_count']}",
    )

    return jsonify(result)
