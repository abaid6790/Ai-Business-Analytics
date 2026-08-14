from datetime import datetime, timezone

from app.extensions import db


class Chart(db.Model):
    __tablename__ = "charts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("datasets.id"), nullable=False, index=True)

    title = db.Column(db.String(255), nullable=False)
    chart_type = db.Column(db.String(50), nullable=False)  # bar, line, pie, scatter, etc.

    # Chart config: x/y axis, aggregation, grouping, filters — stored as JSON
    config_json = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Chart {self.title} type={self.chart_type}>"
