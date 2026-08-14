from datetime import datetime, timezone

from app.extensions import db


class AIUsage(db.Model):
    __tablename__ = "ai_usage"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    provider = db.Column(db.String(50), nullable=False, index=True)
    model = db.Column(db.String(100), nullable=False)

    request_type = db.Column(db.String(50), nullable=True)  # generate, generate_json, stream, analyze
    success = db.Column(db.Boolean, nullable=False, default=True)
    error_message = db.Column(db.Text, nullable=True)

    prompt_tokens = db.Column(db.Integer, nullable=True)
    completion_tokens = db.Column(db.Integer, nullable=True)
    total_tokens = db.Column(db.Integer, nullable=True)

    response_time_ms = db.Column(db.Integer, nullable=True)
    cache_hit = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self):
        return f"<AIUsage user_id={self.user_id} provider={self.provider} success={self.success}>"
