import os

from flask import Flask, render_template

from config import get_config
from app.extensions import db, login_manager, mail, csrf, migrate, limiter
from app.utils.logging_setup import configure_logging


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or get_config())
    _validate_production_config(app)

    _ensure_directories(app)
    configure_logging(app)
    _register_extensions(app)
    _register_blueprints(app)
    _register_login_manager()
    _register_error_handlers(app)
    _register_context_processors(app)

    from app.cli import register_cli
    register_cli(app)

    return app


def _validate_production_config(app):
    """Fails fast at startup rather than silently running with an insecure
    default. Only checked in production — dev/testing intentionally use a
    stable default SECRET_KEY so sessions survive restarts during local work."""
    if app.config.get("DEBUG") is False and app.config.get("SESSION_COOKIE_SECURE") is True:
        if app.config.get("SECRET_KEY") == "dev-secret-key-change-me":
            raise RuntimeError(
                "SECRET_KEY is still set to the insecure development default. "
                "Set a real, random SECRET_KEY in your production environment before starting the app."
            )


def _ensure_directories(app):
    for key in ("UPLOAD_FOLDER", "PROCESSED_FOLDER", "MODELS_FOLDER", "REPORTS_FOLDER", "LOG_FOLDER"):
        path = app.config.get(key)
        if path:
            os.makedirs(path, exist_ok=True)


def _register_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)


def _register_blueprints(app):
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.main import main_bp
    from app.routes.datasets import datasets_bp
    from app.routes.analytics import analytics_bp
    from app.routes.ai_analyst import ai_analyst_bp
    from app.routes.anomaly import anomaly_bp
    from app.routes.ml import ml_bp
    from app.routes.forecasting import forecasting_bp
    from app.routes.reports import reports_bp
    from app.routes.projects import projects_bp
    from app.routes.history import history_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(datasets_bp, url_prefix="/datasets")
    app.register_blueprint(analytics_bp, url_prefix="/analytics")
    app.register_blueprint(ai_analyst_bp, url_prefix="/ai")
    app.register_blueprint(anomaly_bp, url_prefix="/anomaly")
    app.register_blueprint(ml_bp, url_prefix="/ml")
    app.register_blueprint(forecasting_bp, url_prefix="/forecasting")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(projects_bp, url_prefix="/projects")
    app.register_blueprint(history_bp, url_prefix="/history")
    app.register_blueprint(admin_bp, url_prefix="/admin")


def _register_login_manager():
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))


def _register_error_handlers(app):
    @app.errorhandler(413)
    def file_too_large(_error):
        max_mb = app.config.get("MAX_CONTENT_LENGTH_MB", 50)
        return {"error": f"File exceeds the {max_mb}MB upload limit."}, 413

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(error):
        app.logger.exception("Unhandled server error: %s", error)
        return render_template("errors/500.html"), 500


def _register_context_processors(app):
    @app.context_processor
    def inject_globals():
        return {"app_name": "AI Business Analytics Platform"}

    @app.template_filter("from_json")
    def from_json_filter(value):
        import json
        if not value:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None
