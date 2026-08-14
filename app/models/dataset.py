from datetime import datetime, timezone

from app.extensions import db


class Dataset(db.Model):
    __tablename__ = "datasets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("analysis_projects.id"), nullable=True, index=True
    )

    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    file_path = db.Column(db.String(1024), nullable=False)
    original_filename = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # csv, xlsx, xls
    file_size_bytes = db.Column(db.BigInteger, nullable=False, default=0)

    # Denormalized quick-access metadata (populated after processing)
    row_count = db.Column(db.Integer, nullable=True)
    column_count = db.Column(db.Integer, nullable=True)
    missing_values_count = db.Column(db.Integer, nullable=True)
    duplicate_rows_count = db.Column(db.Integer, nullable=True)
    memory_usage_bytes = db.Column(db.BigInteger, nullable=True)
    dtypes_json = db.Column(db.Text, nullable=True)  # JSON-encoded column->dtype map

    # Lineage: cleaned datasets point back to their source, original is never modified
    source_dataset_id = db.Column(db.Integer, db.ForeignKey("datasets.id"), nullable=True)
    is_cleaned_copy = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    cleaned_versions = db.relationship(
        "Dataset",
        backref=db.backref("source_dataset", remote_side=[id]),
        cascade="all, delete-orphan",
        single_parent=True,
    )
    charts = db.relationship(
        "Chart", backref="dataset", lazy="dynamic", cascade="all, delete-orphan"
    )
    ml_models = db.relationship(
        "MLModel", backref="dataset", lazy="dynamic", cascade="all, delete-orphan"
    )
    ai_conversations = db.relationship(
        "AIConversation", backref="dataset", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Dataset {self.name} user_id={self.user_id}>"
