from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)

    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_login_at = db.Column(db.DateTime, nullable=True)

    # --- Relationships (cascade delete: deleting a user removes owned data) ---
    email_verifications = db.relationship(
        "EmailVerification", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )
    password_reset_tokens = db.relationship(
        "PasswordResetToken", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )
    datasets = db.relationship(
        "Dataset", backref="owner", lazy="dynamic", cascade="all, delete-orphan"
    )
    projects = db.relationship(
        "AnalysisProject", backref="owner", lazy="dynamic", cascade="all, delete-orphan"
    )
    ai_conversations = db.relationship(
        "AIConversation", backref="owner", lazy="dynamic", cascade="all, delete-orphan"
    )
    ai_usage_records = db.relationship(
        "AIUsage", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )
    ml_models = db.relationship(
        "MLModel", backref="owner", lazy="dynamic", cascade="all, delete-orphan"
    )
    reports = db.relationship(
        "Report", backref="owner", lazy="dynamic", cascade="all, delete-orphan"
    )
    activity_logs = db.relationship(
        "ActivityLog", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )

    # --- Password helpers ---
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    # Flask-Login integration
    def get_id(self):
        return str(self.id)

    @property
    def is_active(self):
        # Overrides UserMixin.is_active: blocked/disabled accounts can't log in.
        return self.is_active_account

    def __repr__(self):
        return f"<User {self.email}>"
