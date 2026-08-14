from datetime import datetime, timezone

from app.extensions import db


class MLModel(db.Model):
    __tablename__ = "ml_models"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("datasets.id"), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    task_type = db.Column(db.String(20), nullable=False)  # classification, regression
    algorithm = db.Column(db.String(100), nullable=False)  # e.g. RandomForestClassifier
    target_column = db.Column(db.String(255), nullable=False)
    feature_columns_json = db.Column(db.Text, nullable=True)

    metrics_json = db.Column(db.Text, nullable=True)  # accuracy, F1, RMSE, etc.
    feature_importance_json = db.Column(db.Text, nullable=True)
    cv_scores_json = db.Column(db.Text, nullable=True)
    explanation_text = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="pending")  # pending, running, completed, failed
    error_message = db.Column(db.Text, nullable=True)
    training_time_seconds = db.Column(db.Float, nullable=True)
    training_run_id = db.Column(db.String(64), nullable=True, index=True)  # groups models trained together

    model_file_path = db.Column(db.String(1024), nullable=True)
    is_best_model = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<MLModel {self.name} algorithm={self.algorithm}>"
