import json
import os

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.models import Dataset
from app.forms.dataset_forms import DatasetCommitForm, DatasetEditForm
from app.utils.ownership import get_owned_or_404, owner_scoped_query
from app.utils.upload_validation import (
    UploadValidationError,
    validate_extension,
    validate_magic_bytes,
)
from app.utils.activity import log_activity
from app.services.analytics.storage import LocalStorage
from app.services.analytics.dataset_processor import (
    DatasetProfilingError,
    profile_dataset,
    profile_dataframe,
    read_preview_rows,
    read_full_dataframe,
)
from app.services.analytics.column_types import classify_columns
from app.services.analytics.quality_scanner import scan_quality
from app.services.analytics.data_cleaner import apply_cleaning_actions, CleaningError

datasets_bp = Blueprint("datasets", __name__, template_folder="../templates/datasets")


def _storage() -> LocalStorage:
    return LocalStorage(
        upload_folder=current_app.config["UPLOAD_FOLDER"],
        temp_subfolder=current_app.config["DATASET_TEMP_SUBFOLDER"],
    )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@datasets_bp.route("/")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    pagination = (
        owner_scoped_query(Dataset)
        .filter_by(is_cleaned_copy=False)
        .order_by(Dataset.created_at.desc())
        .paginate(page=page, per_page=12, error_out=False)
    )
    return render_template("datasets/index.html", pagination=pagination)


# ---------------------------------------------------------------------------
# Upload — step 1: AJAX preview (validates, saves to temp, profiles it)
# ---------------------------------------------------------------------------
@datasets_bp.route("/upload")
@login_required
def upload_page():
    form = DatasetCommitForm()
    return render_template("datasets/upload.html", form=form)


@datasets_bp.route("/upload/preview", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["UPLOAD_RATE_LIMIT"])
def upload_preview():
    file = request.files.get("file")
    if file is None or file.filename == "":
        return jsonify({"error": "No file was selected."}), 400

    try:
        extension = validate_extension(file.filename)
    except UploadValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    head = file.stream.read(8)
    file.stream.seek(0)
    try:
        validate_magic_bytes(head, extension)
    except UploadValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    storage = _storage()
    temp_filename = storage.save_temp_file(current_user.id, file, extension)
    temp_path = storage.temp_file_path(current_user.id, temp_filename)

    try:
        preview = read_preview_rows(
            temp_path, extension, current_app.config["DATASET_PREVIEW_ROWS"]
        )
        stats = profile_dataset(
            temp_path, extension, current_app.config["DATASET_FULL_PROFILE_MAX_BYTES"]
        )
    except DatasetProfilingError as exc:
        storage.discard_temp_file(current_user.id, temp_filename)
        return jsonify({"error": str(exc)}), 400

    file_size_bytes = os.path.getsize(temp_path)

    return jsonify({
        "temp_filename": temp_filename,
        "original_filename": file.filename,
        "file_type": extension,
        "file_size_bytes": file_size_bytes,
        "preview": preview,
        "stats": stats,
    })


@datasets_bp.route("/upload/discard", methods=["POST"])
@login_required
def upload_discard():
    temp_filename = request.form.get("temp_filename") or (request.json or {}).get("temp_filename")
    if temp_filename:
        _storage().discard_temp_file(current_user.id, temp_filename)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Upload — step 2: commit (name/description + finalize the temp file)
# ---------------------------------------------------------------------------
@datasets_bp.route("/upload/commit", methods=["POST"])
@login_required
def upload_commit():
    form = DatasetCommitForm()
    if not form.validate_on_submit():
        for field_name, errors in form.errors.items():
            for error in errors:
                flash(f"{field_name}: {error}", "danger")
        return redirect(url_for("datasets.upload_page"))

    storage = _storage()
    temp_filename = form.temp_filename.data
    file_type = form.file_type.data

    if not storage.temp_file_exists(current_user.id, temp_filename):
        flash("Your upload expired or was already processed. Please upload again.", "danger")
        return redirect(url_for("datasets.upload_page"))

    temp_path = storage.temp_file_path(current_user.id, temp_filename)

    # Re-profile server-side at commit time rather than trusting any
    # client-supplied stats — the client only ever sees numbers we computed,
    # but we never persist numbers we didn't calculate ourselves just now.
    try:
        stats = profile_dataset(
            temp_path, file_type, current_app.config["DATASET_FULL_PROFILE_MAX_BYTES"]
        )
    except DatasetProfilingError as exc:
        storage.discard_temp_file(current_user.id, temp_filename)
        flash(f"Could not process file: {exc}", "danger")
        return redirect(url_for("datasets.upload_page"))

    permanent_path = storage.commit_temp_file(current_user.id, temp_filename, file_type)

    dataset = Dataset(
        user_id=current_user.id,
        name=form.name.data.strip(),
        description=(form.description.data or "").strip() or None,
        file_path=permanent_path,
        original_filename=form.original_filename.data,
        file_type=file_type,
        file_size_bytes=int(form.file_size_bytes.data),
        row_count=stats["row_count"],
        column_count=stats["column_count"],
        missing_values_count=stats["missing_values_count"],
        duplicate_rows_count=stats["duplicate_rows_count"],
        memory_usage_bytes=stats["memory_usage_bytes"],
        dtypes_json=stats["dtypes_json"],
    )
    db.session.add(dataset)
    db.session.commit()

    log_activity(current_user.id, "dataset_upload", f"dataset_id={dataset.id} name={dataset.name}")
    flash("Dataset uploaded successfully.", "success")
    return redirect(url_for("datasets.detail", dataset_id=dataset.id))


# ---------------------------------------------------------------------------
# Detail / edit / delete
# ---------------------------------------------------------------------------
@datasets_bp.route("/<int:dataset_id>")
@login_required
def detail(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    dtypes = json.loads(dataset.dtypes_json) if dataset.dtypes_json else {}

    # Re-derive the numeric/categorical/date breakdown using the same
    # classify_columns() heuristic every other route (forecasting, ML,
    # anomaly detection) relies on. Guessing from the raw stored dtype
    # string doesn't work here: pandas never auto-infers CSV date columns
    # as datetime64 on read, so a string-based check would silently never
    # detect date columns and features gated on "has a date column" (like
    # the Forecast button) would never appear.
    numeric_cols, categorical_cols, datetime_cols = [], [], []
    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
        classification = classify_columns(df)
        numeric_cols = classification["numeric_columns"]
        categorical_cols = classification["categorical_columns"]
        datetime_cols = classification["datetime_columns"]
    except DatasetProfilingError:
        pass  # fall back to empty lists rather than failing the whole page

    return render_template(
        "datasets/detail.html",
        dataset=dataset,
        dtypes=dtypes,
        numeric_cols=numeric_cols,
        categorical_cols=categorical_cols,
        datetime_cols=datetime_cols,
    )


@datasets_bp.route("/<int:dataset_id>/edit", methods=["GET", "POST"])
@login_required
def edit(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    form = DatasetEditForm(obj=dataset)

    if form.validate_on_submit():
        dataset.name = form.name.data.strip()
        dataset.description = (form.description.data or "").strip() or None
        db.session.commit()
        flash("Dataset updated.", "success")
        return redirect(url_for("datasets.detail", dataset_id=dataset.id))

    return render_template("datasets/edit.html", form=form, dataset=dataset)


@datasets_bp.route("/<int:dataset_id>/delete", methods=["POST"])
@login_required
def delete(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    storage = _storage()

    # Delete cleaned copies' files too before the DB cascade removes the rows.
    for cleaned in list(dataset.cleaned_versions):
        storage.delete_file(cleaned.file_path)
    storage.delete_file(dataset.file_path)

    name = dataset.name
    db.session.delete(dataset)
    db.session.commit()

    log_activity(current_user.id, "dataset_delete", f"dataset_id={dataset_id} name={name}")
    flash("Dataset deleted.", "info")
    return redirect(url_for("datasets.index"))


# ---------------------------------------------------------------------------
# Data cleaning (Phase 5)
# ---------------------------------------------------------------------------
@datasets_bp.route("/<int:dataset_id>/clean")
@login_required
def clean(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)

    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
        quality = scan_quality(df)
    except DatasetProfilingError as exc:
        flash(f"Could not analyze this dataset: {exc}", "danger")
        return redirect(url_for("datasets.detail", dataset_id=dataset.id))

    columns = list(df.columns.astype(str))
    numeric_columns = [c for c in columns if str(df[c].dtype).startswith(("int", "float"))]

    return render_template(
        "datasets/clean.html",
        dataset=dataset,
        quality=quality,
        columns=columns,
        numeric_columns=numeric_columns,
    )


@datasets_bp.route("/<int:dataset_id>/clean/apply", methods=["POST"])
@login_required
def clean_apply(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)

    actions = _parse_cleaning_actions(request.form)
    if not actions:
        flash("Select at least one cleaning action to apply.", "warning")
        return redirect(url_for("datasets.clean", dataset_id=dataset.id))

    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
        cleaned_df, applied_log = apply_cleaning_actions(df, actions)
        stats = profile_dataframe(cleaned_df)
    except (DatasetProfilingError, CleaningError) as exc:
        flash(f"Cleaning failed: {exc}", "danger")
        return redirect(url_for("datasets.clean", dataset_id=dataset.id))

    storage = _storage()
    permanent_path, actual_file_type = storage.save_cleaned_dataframe(
        current_user.id, cleaned_df, dataset.file_type
    )
    file_size_bytes = os.path.getsize(permanent_path)

    cleaned_name = f"{dataset.name} (cleaned)"
    cleaned_dataset = Dataset(
        user_id=current_user.id,
        project_id=dataset.project_id,
        name=cleaned_name,
        description=f"Cleaned copy of '{dataset.name}'. Actions applied: " + "; ".join(applied_log),
        file_path=permanent_path,
        original_filename=dataset.original_filename,
        file_type=actual_file_type,
        file_size_bytes=file_size_bytes,
        row_count=stats["row_count"],
        column_count=stats["column_count"],
        missing_values_count=stats["missing_values_count"],
        duplicate_rows_count=stats["duplicate_rows_count"],
        memory_usage_bytes=stats["memory_usage_bytes"],
        dtypes_json=stats["dtypes_json"],
        source_dataset_id=dataset.id,
        is_cleaned_copy=True,
    )
    db.session.add(cleaned_dataset)
    db.session.commit()

    log_activity(
        current_user.id,
        "dataset_cleaned",
        f"source_id={dataset.id} cleaned_id={cleaned_dataset.id} actions={len(actions)}",
    )
    flash(f"Cleaned dataset created: {cleaned_name}", "success")
    return redirect(url_for("datasets.compare", dataset_id=cleaned_dataset.id))


@datasets_bp.route("/<int:dataset_id>/compare")
@login_required
def compare(dataset_id):
    cleaned = get_owned_or_404(Dataset, dataset_id)
    if not cleaned.is_cleaned_copy or cleaned.source_dataset_id is None:
        flash("This dataset has no before/after comparison available.", "info")
        return redirect(url_for("datasets.detail", dataset_id=cleaned.id))

    original = get_owned_or_404(Dataset, cleaned.source_dataset_id)
    return render_template("datasets/compare.html", original=original, cleaned=cleaned)


def _parse_cleaning_actions(form) -> list:
    """
    Parses checkbox/select inputs from the cleaning form into a list of
    action dicts consumed by apply_cleaning_actions(). Only whitelisted
    action types reach the cleaning engine — nothing here executes
    arbitrary code or user-supplied expressions.
    """
    actions = []

    if form.get("remove_duplicates") == "on":
        actions.append({"type": "remove_duplicates"})

    for column in form.getlist("drop_column"):
        actions.append({"type": "drop_column", "column": column})

    # Per-column missing-value handling: fill_missing__<col>=<strategy>|drop
    for key, value in form.items():
        if not key.startswith("missing__") or not value:
            continue
        column = key[len("missing__"):]
        if value == "drop":
            actions.append({"type": "drop_missing", "column": column})
        elif value in ("mean", "median", "mode", "zero"):
            actions.append({"type": "fill_missing", "column": column, "strategy": value})

    # Per-column type conversion: convert__<col>=<target_type>
    for key, value in form.items():
        if not key.startswith("convert__") or not value or value == "none":
            continue
        column = key[len("convert__"):]
        actions.append({"type": "convert_type", "column": column, "target_type": value})

    # Per-column outlier handling: outliers__<col>=clip|remove
    for key, value in form.items():
        if not key.startswith("outliers__") or not value or value == "none":
            continue
        column = key[len("outliers__"):]
        actions.append({"type": "handle_outliers", "column": column, "method": value})

    return actions
