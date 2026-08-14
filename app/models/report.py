from datetime import datetime, timezone

from app.extensions import db


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("analysis_projects.id"), nullable=True, index=True
    )

    title = db.Column(db.String(255), nullable=False)
    format = db.Column(db.String(10), nullable=False)  # pdf, xlsx, csv, json
    file_path = db.Column(db.String(1024), nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Report {self.title} format={self.format}>"
