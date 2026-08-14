from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import AnalysisProject, Dataset, Report
from app.utils.ownership import get_owned_or_404, owner_scoped_query
from app.utils.activity import log_activity

projects_bp = Blueprint("projects", __name__, template_folder="../templates/projects")


@projects_bp.route("/")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    pagination = owner_scoped_query(AnalysisProject).order_by(AnalysisProject.updated_at.desc()).paginate(page=page, per_page=24, error_out=False)
    return render_template("projects/index.html", pagination=pagination)


@projects_bp.route("/create", methods=["POST"])
@login_required
def create():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None

    if not name:
        flash("Please provide a project name.", "danger")
        return redirect(url_for("projects.index"))

    project = AnalysisProject(user_id=current_user.id, name=name, description=description)
    db.session.add(project)
    db.session.commit()

    log_activity(current_user.id, "project_created", f"project_id={project.id} name={name}")
    flash("Project created.", "success")
    return redirect(url_for("projects.detail", project_id=project.id))


@projects_bp.route("/<int:project_id>")
@login_required
def detail(project_id):
    project = get_owned_or_404(AnalysisProject, project_id)

    datasets_in_project = (
        owner_scoped_query(Dataset).filter_by(project_id=project.id, is_cleaned_copy=False).all()
    )
    unassigned_datasets = (
        owner_scoped_query(Dataset)
        .filter(Dataset.project_id.is_(None), Dataset.is_cleaned_copy.is_(False))
        .all()
    )
    reports = project.reports.order_by(Report.created_at.desc()).all()

    return render_template(
        "projects/detail.html",
        project=project,
        datasets_in_project=datasets_in_project,
        unassigned_datasets=unassigned_datasets,
        reports=reports,
    )


@projects_bp.route("/<int:project_id>/edit", methods=["POST"])
@login_required
def edit(project_id):
    project = get_owned_or_404(AnalysisProject, project_id)
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None

    if not name:
        flash("Please provide a project name.", "danger")
        return redirect(url_for("projects.detail", project_id=project.id))

    project.name = name
    project.description = description
    db.session.commit()
    flash("Project updated.", "success")
    return redirect(url_for("projects.detail", project_id=project.id))


@projects_bp.route("/<int:project_id>/delete", methods=["POST"])
@login_required
def delete(project_id):
    project = get_owned_or_404(AnalysisProject, project_id)

    # Datasets aren't cascade-deleted with the project — they just become
    # unassigned, since a dataset can meaningfully exist without a project.
    for dataset in project.datasets:
        dataset.project_id = None

    db.session.delete(project)
    db.session.commit()

    log_activity(current_user.id, "project_deleted", f"project_id={project_id}")
    flash("Project deleted. Its datasets were kept and unassigned.", "info")
    return redirect(url_for("projects.index"))


@projects_bp.route("/<int:project_id>/add-dataset", methods=["POST"])
@login_required
def add_dataset(project_id):
    project = get_owned_or_404(AnalysisProject, project_id)
    dataset_id = request.form.get("dataset_id", type=int)
    if not dataset_id:
        flash("Select a dataset to add.", "danger")
        return redirect(url_for("projects.detail", project_id=project.id))

    dataset = get_owned_or_404(Dataset, dataset_id)
    dataset.project_id = project.id
    db.session.commit()

    flash(f"Added '{dataset.name}' to project.", "success")
    return redirect(url_for("projects.detail", project_id=project.id))


@projects_bp.route("/<int:project_id>/remove-dataset/<int:dataset_id>", methods=["POST"])
@login_required
def remove_dataset(project_id, dataset_id):
    project = get_owned_or_404(AnalysisProject, project_id)
    dataset = get_owned_or_404(Dataset, dataset_id)

    if dataset.project_id == project.id:
        dataset.project_id = None
        db.session.commit()
        flash(f"Removed '{dataset.name}' from project.", "info")

    return redirect(url_for("projects.detail", project_id=project.id))
