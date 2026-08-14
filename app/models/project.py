from datetime import datetime, timezone

from app.extensions import db


class AnalysisProject(db.Model):
    __tablename__ = "analysis_projects"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    datasets = db.relationship("Dataset", backref="project", lazy="dynamic")
    reports = db.relationship(
        "Report", backref="project", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AnalysisProject {self.name} user_id={self.user_id}>"
