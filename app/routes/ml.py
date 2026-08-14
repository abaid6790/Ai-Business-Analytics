import json

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.models import Dataset, MLModel
from app.utils.ownership import get_owned_or_404, owner_scoped_query
from app.utils.activity import log_activity
from app.services.analytics.dataset_processor import read_full_dataframe, DatasetProfilingError
from app.services.ml.task_detector import detect_task_type, TaskDetectionError
from app.services.ml.model_registry import algorithms_for_task
from app.services.ml.job_runner import submit_training_job, new_training_run_id
from app.services.ml.storage import load_model, delete_model

ml_bp = Blueprint("ml", __name__, template_folder="../templates/ml")


def _load_dataframe_or_none(dataset):
    try:
        return read_full_dataframe(dataset.file_path, dataset.file_type), None
    except DatasetProfilingError as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# Target/feature selection + kickoff
# ---------------------------------------------------------------------------
@ml_bp.route("/<int:dataset_id>")
@login_required
def index(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    df, error = _load_dataframe_or_none(dataset)
    if df is None:
        flash(f"Could not analyze this dataset: {error}", "danger")
        return redirect(url_for("datasets.detail", dataset_id=dataset.id))

    columns = list(df.columns.astype(str))

    models = (
        owner_scoped_query(MLModel)
        .filter_by(dataset_id=dataset.id)
        .order_by(MLModel.created_at.desc())
        .all()
    )

    return render_template("ml/index.html", dataset=dataset, columns=columns, models=models)


@ml_bp.route("/<int:dataset_id>/train", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["ML_TRAIN_RATE_LIMIT"])
def train(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    df, error = _load_dataframe_or_none(dataset)
    if df is None:
        return jsonify({"error": error}), 400

    body = request.get_json(force=True, silent=True) or {}
    target_column = body.get("target_column")
    feature_columns = body.get("feature_columns") or []

    if not target_column or target_column not in df.columns:
        return jsonify({"error": "Please select a valid target column."}), 400
    if not feature_columns:
        feature_columns = [c for c in df.columns if c != target_column]
    else:
        invalid = [c for c in feature_columns if c not in df.columns]
        if invalid:
            return jsonify({"error": f"Unknown feature column(s): {', '.join(invalid)}"}), 400
    if target_column in feature_columns:
        feature_columns = [c for c in feature_columns if c != target_column]
    if not feature_columns:
        return jsonify({"error": "Select at least one feature column."}), 400

    try:
        task_type = detect_task_type(df[target_column])
    except TaskDetectionError as exc:
        return jsonify({"error": str(exc)}), 400

    algorithms = algorithms_for_task(task_type)
    training_run_id = new_training_run_id()

    model_ids_by_algorithm = {}
    for algo_name in algorithms:
        ml_model = MLModel(
            user_id=current_user.id,
            dataset_id=dataset.id,
            name=f"{algo_name} \u2014 {target_column}",
            task_type=task_type,
            algorithm=algo_name,
            target_column=target_column,
            feature_columns_json=json.dumps(feature_columns),
            status="pending",
            training_run_id=training_run_id,
        )
        db.session.add(ml_model)
        db.session.flush()  # get the id without committing yet
        model_ids_by_algorithm[algo_name] = ml_model.id

    db.session.commit()

    submit_training_job(
        current_app._get_current_object(), dataset.id, current_user.id,
        target_column, feature_columns, model_ids_by_algorithm, training_run_id,
    )

    log_activity(
        current_user.id, "ml_training_started",
        f"dataset_id={dataset.id} target={target_column} task_type={task_type} run_id={training_run_id}",
    )

    return jsonify({
        "training_run_id": training_run_id,
        "task_type": task_type,
        "model_ids": list(model_ids_by_algorithm.values()),
    })


@ml_bp.route("/<int:dataset_id>/status")
@login_required
def status(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    training_run_id = request.args.get("training_run_id")

    query = owner_scoped_query(MLModel).filter_by(dataset_id=dataset.id)
    if training_run_id:
        query = query.filter_by(training_run_id=training_run_id)

    models = query.order_by(MLModel.created_at.desc()).all()
    return jsonify({"models": [_model_summary(m) for m in models]})


def _model_summary(m):
    return {
        "id": m.id,
        "algorithm": m.algorithm,
        "status": m.status,
        "error_message": m.error_message,
        "metrics": json.loads(m.metrics_json) if m.metrics_json else None,
        "is_best_model": m.is_best_model,
        "training_time_seconds": m.training_time_seconds,
    }


# ---------------------------------------------------------------------------
# Model detail / delete / predict
# ---------------------------------------------------------------------------
@ml_bp.route("/models/<int:model_id>")
@login_required
def model_detail(model_id):
    ml_model = get_owned_or_404(MLModel, model_id)

    metrics = json.loads(ml_model.metrics_json) if ml_model.metrics_json else None
    cv_scores = json.loads(ml_model.cv_scores_json) if ml_model.cv_scores_json else None
    feature_importance = json.loads(ml_model.feature_importance_json) if ml_model.feature_importance_json else None
    feature_columns = json.loads(ml_model.feature_columns_json) if ml_model.feature_columns_json else []

    return render_template(
        "ml/model_detail.html",
        model=ml_model,
        metrics=metrics,
        cv_scores=cv_scores,
        feature_importance=feature_importance,
        feature_columns=feature_columns,
    )


@ml_bp.route("/models/<int:model_id>/delete", methods=["POST"])
@login_required
def model_delete(model_id):
    ml_model = get_owned_or_404(MLModel, model_id)
    dataset_id = ml_model.dataset_id
    delete_model(ml_model.model_file_path)
    db.session.delete(ml_model)
    db.session.commit()
    flash("Model deleted.", "info")
    return redirect(url_for("ml.index", dataset_id=dataset_id))


@ml_bp.route("/models/<int:model_id>/predict", methods=["POST"])
@login_required
def predict(model_id):
    ml_model = get_owned_or_404(MLModel, model_id)

    if ml_model.status != "completed" or not ml_model.model_file_path:
        return jsonify({"error": "This model is not ready for predictions."}), 400

    body = request.get_json(force=True, silent=True) or {}
    feature_columns = json.loads(ml_model.feature_columns_json) if ml_model.feature_columns_json else []

    missing = [c for c in feature_columns if c not in body]
    if missing:
        return jsonify({"error": f"Missing value(s) for: {', '.join(missing)}"}), 400

    import pandas as pd
    row = {c: body[c] for c in feature_columns}
    input_df = pd.DataFrame([row])

    try:
        pipeline = load_model(ml_model.model_file_path)
        prediction = pipeline.predict(input_df)[0]
        result = {"prediction": _jsonable(prediction)}
        if hasattr(pipeline.named_steps.get("estimator"), "predict_proba"):
            proba = pipeline.predict_proba(input_df)[0]
            result["probabilities"] = [round(float(p), 4) for p in proba]
    except Exception as exc:
        return jsonify({"error": f"Prediction failed: {exc}"}), 400

    return jsonify(result)


def _jsonable(value):
    import numpy as np
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return round(float(value), 6)
    return value
