from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import Dataset, AnalysisProject, AIConversation, MLModel, Report

dashboard_bp = Blueprint("dashboard", __name__, template_folder="../templates/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    datasets = Dataset.query.filter_by(user_id=current_user.id, is_cleaned_copy=False)
    total_datasets = datasets.count()

    total_rows = sum(d.row_count or 0 for d in datasets)
    total_columns = sum(d.column_count or 0 for d in datasets)

    total_analyses = AnalysisProject.query.filter_by(user_id=current_user.id).count()
    total_ai_questions = AIConversation.query.filter_by(user_id=current_user.id).count()
    total_ml_models = MLModel.query.filter_by(user_id=current_user.id).count()

    storage_bytes = sum(d.file_size_bytes or 0 for d in Dataset.query.filter_by(user_id=current_user.id))
    storage_mb = round(storage_bytes / (1024 * 1024), 2)

    recent_datasets = (
        Dataset.query.filter_by(user_id=current_user.id)
        .order_by(Dataset.created_at.desc())
        .limit(5)
        .all()
    )
    recent_reports = (
        Report.query.filter_by(user_id=current_user.id)
        .order_by(Report.created_at.desc())
        .limit(5)
        .all()
    )
    recent_conversations = (
        AIConversation.query.filter_by(user_id=current_user.id)
        .order_by(AIConversation.updated_at.desc())
        .limit(5)
        .all()
    )

    stats = {
        "total_datasets": total_datasets,
        "total_analyses": total_analyses,
        "total_rows": total_rows,
        "total_columns": total_columns,
        "total_ai_questions": total_ai_questions,
        "total_ml_models": total_ml_models,
        "storage_mb": storage_mb,
    }

    return render_template(
        "dashboard/index.html",
        stats=stats,
        recent_datasets=recent_datasets,
        recent_reports=recent_reports,
        recent_conversations=recent_conversations,
    )
