from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify

from flask_login import login_required, current_user

from app.models import Dataset
from app.utils.ownership import get_owned_or_404
from app.utils.activity import log_activity
from app.services.analytics.dataset_processor import read_full_dataframe, DatasetProfilingError
from app.services.analytics.column_types import classify_columns
from app.services.forecasting.preparer import prepare_series, TimeSeriesError
from app.services.forecasting.forecaster import generate_forecast, ForecastError

forecasting_bp = Blueprint("forecasting", __name__, template_folder="../templates/forecasting")


@forecasting_bp.route("/<int:dataset_id>")
@login_required
def index(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
    except DatasetProfilingError as exc:
        flash(f"Could not analyze this dataset: {exc}", "danger")
        return redirect(url_for("datasets.detail", dataset_id=dataset.id))

    classification = classify_columns(df)
    date_columns = classification["datetime_columns"]
    numeric_columns = classification["numeric_columns"]

    return render_template(
        "forecasting/index.html",
        dataset=dataset,
        date_columns=date_columns,
        numeric_columns=numeric_columns,
    )


@forecasting_bp.route("/<int:dataset_id>/generate", methods=["POST"])
@login_required
def generate(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
    except DatasetProfilingError as exc:
        return jsonify({"error": str(exc)}), 400

    body = request.get_json(force=True, silent=True) or {}
    date_column = body.get("date_column")
    value_column = body.get("value_column")
    periods = int(body.get("periods", 12))
    freq_override = body.get("freq") or None

    if not date_column or not value_column:
        return jsonify({"error": "Select both a date column and a value column."}), 400

    try:
        prepared = prepare_series(df, date_column, value_column, freq=freq_override)
        result = generate_forecast(prepared["series"], prepared["freq"], periods)
    except (TimeSeriesError, ForecastError) as exc:
        return jsonify({"error": str(exc)}), 400

    result["freq"] = prepared["freq"]
    result["freq_label"] = prepared["freq_label"]
    result["date_column"] = date_column
    result["value_column"] = value_column

    log_activity(
        current_user.id, "forecast_generated",
        f"dataset_id={dataset.id} date_col={date_column} value_col={value_column} method={result['method']}",
    )

    return jsonify(result)
