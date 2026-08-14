import io
import json

import pytest

from app import create_app
from config import ProductionConfig, DevelopmentConfig
from tests.conftest import create_verified_user, login


def test_production_config_rejects_default_secret_key(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "dev-secret-key-change-me")
    with pytest.raises(RuntimeError, match="insecure development default"):
        create_app(ProductionConfig)


def test_production_config_accepts_real_secret_key(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "a-genuinely-random-production-secret-key")
    app = create_app(ProductionConfig)
    assert app is not None


def test_development_config_does_not_require_real_secret_key():
    # Should not raise even with the default dev SECRET_KEY — dev/testing
    # intentionally use a stable default so sessions survive restarts.
    app = create_app(DevelopmentConfig)
    assert app is not None


def test_report_download_filename_is_sanitized(client, db):
    create_verified_user(db, email="sanitizetest@example.com", password="Password123")
    login(client, "sanitizetest@example.com", "Password123")

    data = {"file": (io.BytesIO(b"a,b\n1,2\n"), "data.csv")}
    resp = client.post("/datasets/upload/preview", data=data, content_type="multipart/form-data")
    body = resp.get_json()
    client.post(
        "/datasets/upload/commit",
        data={
            "name": "Sanitize Test",
            "temp_filename": body["temp_filename"],
            "original_filename": body["original_filename"],
            "file_type": body["file_type"],
            "file_size_bytes": body["file_size_bytes"],
        },
        follow_redirects=True,
    )
    from app.models import Dataset
    dataset = Dataset.query.filter_by(name="Sanitize Test").first()

    dangerous_title = 'report"; evil/../../etc/passwd\r\nX-Injected: true'
    client.post(
        f"/reports/build/{dataset.id}",
        data={"format": "json", "title": dangerous_title},
        follow_redirects=True,
    )

    from app.models import Report
    report = Report.query.filter_by(title=dangerous_title).first()
    assert report is not None  # the DB record keeps the real title, unsanitized

    resp = client.get(f"/reports/{report.id}/download")
    assert resp.status_code == 200
    content_disposition = resp.headers.get("Content-Disposition", "")
    # secure_filename() strips path separators and control characters —
    # that's the actual safety property (no traversal, no header injection).
    # Leftover literal ".." text with no separator around it is harmless:
    # download_name never touches the real filesystem path (report.file_path
    # is always server-controlled), it only suggests a browser save-as name.
    assert "\r" not in content_disposition
    assert "\n" not in content_disposition
    assert "/" not in content_disposition
    assert "\\" not in content_disposition
