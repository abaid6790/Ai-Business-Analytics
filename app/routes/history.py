from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models import ActivityLog
from app.utils.ownership import owner_scoped_query

history_bp = Blueprint("history", __name__, template_folder="../templates/history")

PER_PAGE = 30


@history_bp.route("/")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    pagination = (
        owner_scoped_query(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .paginate(page=page, per_page=PER_PAGE, error_out=False)
    )
    return render_template("history/index.html", pagination=pagination)
