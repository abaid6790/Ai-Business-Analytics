from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models import User, Dataset, AIUsage, ActivityLog
from app.services.ai import get_provider_manager
from app.services.system_settings import set_setting
from app.utils.activity import log_activity

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")

KNOWN_PROVIDER_NAMES = ["gemini", "groq", "openrouter", "claude", "openai"]


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active_account=True).count()
    dataset_count = Dataset.query.filter_by(is_cleaned_copy=False).count()

    ai_requests = AIUsage.query.count()
    failed_ai_requests = AIUsage.query.filter_by(success=False).count()

    provider_usage = (
        db.session.query(AIUsage.provider, db.func.count(AIUsage.id))
        .group_by(AIUsage.provider)
        .all()
    )

    manager = get_provider_manager(current_app)

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        active_users=active_users,
        dataset_count=dataset_count,
        ai_requests=ai_requests,
        failed_ai_requests=failed_ai_requests,
        provider_usage=provider_usage,
        configured_providers=manager.configured_provider_order(),
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------
@admin_bp.route("/users")
@login_required
@admin_required
def users():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()

    query = User.query
    if search:
        query = query.filter(User.email.ilike(f"%{search}%"))

    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("admin/users.html", pagination=pagination, search=search)


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_active(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.id == current_user.id:
        flash("You can't disable your own account.", "danger")
        return redirect(url_for("admin.users"))

    user.is_active_account = not user.is_active_account
    db.session.commit()

    log_activity(current_user.id, "admin_user_toggled_active", f"target_user_id={user.id} active={user.is_active_account}")
    flash(f"{'Enabled' if user.is_active_account else 'Disabled'} account for {user.email}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.id == current_user.id:
        flash("You can't delete your own account from here.", "danger")
        return redirect(url_for("admin.users"))

    email = user.email
    db.session.delete(user)
    db.session.commit()

    log_activity(current_user.id, "admin_user_deleted", f"deleted_email={email}")
    flash(f"Deleted account: {email}.", "info")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------------
# System logs
# ---------------------------------------------------------------------------
@admin_bp.route("/logs")
@login_required
@admin_required
def logs():
    page = request.args.get("page", 1, type=int)
    pagination = (
        ActivityLog.query.order_by(ActivityLog.created_at.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )
    return render_template("admin/logs.html", pagination=pagination)


# ---------------------------------------------------------------------------
# AI provider management
# ---------------------------------------------------------------------------
@admin_bp.route("/ai-providers")
@login_required
@admin_required
def ai_providers():
    manager = get_provider_manager(current_app)

    gemini_stats = None
    gemini_pool = manager.providers.get("gemini")
    if gemini_pool is not None and hasattr(gemini_pool, "stats"):
        gemini_stats = gemini_pool.stats()

    usage_by_provider = (
        db.session.query(
            AIUsage.provider,
            db.func.count(AIUsage.id),
            db.func.sum(db.case((AIUsage.success.is_(False), 1), else_=0)),
        )
        .group_by(AIUsage.provider)
        .all()
    )

    return render_template(
        "admin/ai_providers.html",
        configured_providers=list(manager.providers.keys()),
        provider_order=manager.provider_order,
        known_provider_names=KNOWN_PROVIDER_NAMES,
        gemini_stats=gemini_stats,
        usage_by_provider=usage_by_provider,
        daily_limit=manager.config.get("AI_DAILY_REQUEST_LIMIT_PER_USER"),
        monthly_limit=manager.config.get("AI_MONTHLY_REQUEST_LIMIT_PER_USER"),
    )


@admin_bp.route("/ai-providers/limits", methods=["POST"])
@login_required
@admin_required
def update_limits():
    daily = request.form.get("daily_limit", type=int)
    monthly = request.form.get("monthly_limit", type=int)

    if daily is None or daily < 1 or monthly is None or monthly < 1:
        flash("Limits must be positive numbers.", "danger")
        return redirect(url_for("admin.ai_providers"))

    set_setting("AI_DAILY_REQUEST_LIMIT_PER_USER", str(daily))
    set_setting("AI_MONTHLY_REQUEST_LIMIT_PER_USER", str(monthly))

    manager = get_provider_manager(current_app)
    manager.update_limits(daily=daily, monthly=monthly)

    log_activity(current_user.id, "admin_updated_ai_limits", f"daily={daily} monthly={monthly}")
    flash("Usage limits updated.", "success")
    return redirect(url_for("admin.ai_providers"))


@admin_bp.route("/ai-providers/order", methods=["POST"])
@login_required
@admin_required
def update_order():
    raw_order = request.form.get("provider_order", "")
    new_order = [p.strip() for p in raw_order.split(",") if p.strip()]

    invalid = [p for p in new_order if p not in KNOWN_PROVIDER_NAMES]
    if invalid:
        flash(f"Unknown provider name(s): {', '.join(invalid)}.", "danger")
        return redirect(url_for("admin.ai_providers"))
    if not new_order:
        flash("Provide at least one provider in the fallback order.", "danger")
        return redirect(url_for("admin.ai_providers"))

    set_setting("AI_PROVIDER_ORDER", ",".join(new_order))

    manager = get_provider_manager(current_app)
    manager.update_provider_order(new_order)

    log_activity(current_user.id, "admin_updated_provider_order", f"order={new_order}")
    flash("AI provider fallback order updated.", "success")
    return redirect(url_for("admin.ai_providers"))
