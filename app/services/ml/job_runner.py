"""
Runs a full training job (all algorithms for a task type) on a background
thread so the upload-a-target-and-train request returns immediately
instead of blocking on what can be a multi-minute operation (spec section
31 performance notes, and section 12's model-comparison requirement).

This is a simple ThreadPoolExecutor, not Celery/RQ — an intentional MVP
choice documented in the phased roadmap. It's correct for a single-process
dev/small deployment; moving to a real task queue for multi-worker
production deployments is a scoped follow-up that doesn't change any of
the training logic here, only how this function gets invoked.
"""

import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from app.services.ml.evaluator import primary_metric
from app.services.ml.model_registry import algorithms_for_task
from app.services.ml.pipeline_builder import classify_features
from app.services.ml.storage import save_model
from app.services.ml.trainer import train_single_model

_executor = ThreadPoolExecutor(max_workers=8)


def new_training_run_id() -> str:
    return uuid.uuid4().hex


def submit_training_job(app, dataset_id, user_id, target_column, feature_columns, model_ids_by_algorithm, training_run_id):
    """
    Fire-and-forget: submits the actual training work to the thread pool.
    `model_ids_by_algorithm` maps algorithm_name -> MLModel.id (rows
    already created with status='pending' by the route, so the UI has
    something to poll immediately).
    """
    _executor.submit(
        _run_training_job, app, dataset_id, user_id, target_column,
        feature_columns, model_ids_by_algorithm, training_run_id,
    )


def _run_training_job(app, dataset_id, user_id, target_column, feature_columns, model_ids_by_algorithm, training_run_id):
    with app.app_context():
        from app.extensions import db
        from app.models import Dataset, MLModel
        from app.services.analytics.dataset_processor import read_full_dataframe
        from app.services.ml.task_detector import detect_task_type

        try:
            _run_training_job_inner(
                db, app, dataset_id, user_id, target_column, feature_columns,
                model_ids_by_algorithm, Dataset, MLModel, read_full_dataframe, detect_task_type,
            )
        finally:
            db.session.remove()


def _run_training_job_inner(db, app, dataset_id, user_id, target_column, feature_columns,
                             model_ids_by_algorithm, Dataset, MLModel, read_full_dataframe, detect_task_type):
    dataset = db.session.get(Dataset, dataset_id)
    if dataset is None:
        return

    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
    except Exception as exc:
        _mark_all_failed(db, model_ids_by_algorithm, f"Could not read dataset: {exc}")
        return

    try:
        df = df.dropna(subset=[target_column])
        y = df[target_column]
        task_type = detect_task_type(y)
        classification = classify_features(df, feature_columns)
        X = df[feature_columns]
    except Exception as exc:
        _mark_all_failed(db, model_ids_by_algorithm, f"Setup failed: {exc}")
        return

    results = []
    algorithms = algorithms_for_task(task_type)

    for algo_name, algo_factory in algorithms.items():
        model_id = model_ids_by_algorithm.get(algo_name)
        if model_id is None:
            continue

        ml_model = db.session.get(MLModel, model_id)
        if ml_model is None:
            continue

        ml_model.status = "running"
        db.session.commit()

        try:
            result = train_single_model(
                X, y,
                classification["numeric_features"], classification["categorical_features"],
                algo_factory, task_type, target_column, algo_name,
            )
            model_path = save_model(app.config["MODELS_FOLDER"], user_id, result["pipeline"])

            ml_model.status = "completed"
            ml_model.metrics_json = json.dumps(result["metrics"])
            ml_model.cv_scores_json = json.dumps(result["cv_scores"]) if result["cv_scores"] else None
            ml_model.feature_importance_json = json.dumps(result["feature_importance"])
            ml_model.explanation_text = result["explanation_text"]
            ml_model.training_time_seconds = result["training_time_seconds"]
            ml_model.model_file_path = model_path
            db.session.commit()

            results.append((ml_model, task_type, result["metrics"]))
        except Exception as exc:
            ml_model.status = "failed"
            ml_model.error_message = str(exc)
            db.session.commit()

    _mark_best_model(db, results, task_type if results else None)


def _mark_all_failed(db, model_ids_by_algorithm, message):
    from app.models import MLModel

    for model_id in model_ids_by_algorithm.values():
        ml_model = db.session.get(MLModel, model_id)
        if ml_model:
            ml_model.status = "failed"
            ml_model.error_message = message
    db.session.commit()


def _mark_best_model(db, results, task_type):
    if not results:
        return
    best = max(results, key=lambda r: primary_metric(task_type, r[2]))
    best[0].is_best_model = True
    db.session.commit()
