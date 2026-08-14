import io

from app.models import Dataset
from tests.conftest import create_verified_user, login

CSV_CONTENT = b"name,age,signup_date,revenue\nAlice,30,2024-01-05,120.5\nBob,25,2024-01-06,80.0\nAlice,30,2024-01-05,120.5\n"
EMPTY_CSV = b""
BINARY_FAKE_CSV = b"\x00\x01\x02not,really,csv\n"


def _upload(client, csrf_headers, filename=b"data.csv", content=CSV_CONTENT, content_type="text/csv"):
    data = {"file": (io.BytesIO(content), filename.decode() if isinstance(filename, bytes) else filename)}
    return client.post(
        "/datasets/upload/preview",
        data=data,
        content_type="multipart/form-data",
        headers=csrf_headers,
    )


def _get_csrf_headers(client):
    # In TestingConfig CSRF is disabled, but keep header plumbing realistic.
    return {"X-CSRFToken": "test"}


def test_upload_preview_returns_stats_and_rows(client, db):
    create_verified_user(db, email="uploader@example.com", password="Password123")
    login(client, "uploader@example.com", "Password123")

    resp = _upload(client, _get_csrf_headers(client))
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["stats"]["row_count"] == 3
    assert body["stats"]["column_count"] == 4
    assert body["stats"]["duplicate_rows_count"] == 1
    assert "revenue" in body["stats"]["numeric_columns"]
    assert "name" in body["stats"]["categorical_columns"]
    assert len(body["preview"]["rows"]) == 3
    assert body["temp_filename"].endswith(".csv")


def test_upload_rejects_disallowed_extension(client, db):
    create_verified_user(db, email="badext@example.com", password="Password123")
    login(client, "badext@example.com", "Password123")

    resp = _upload(client, _get_csrf_headers(client), filename="malware.exe", content=b"whatever")
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.get_json()["error"]


def test_upload_rejects_empty_file(client, db):
    create_verified_user(db, email="emptyfile@example.com", password="Password123")
    login(client, "emptyfile@example.com", "Password123")

    resp = _upload(client, _get_csrf_headers(client), content=EMPTY_CSV)
    assert resp.status_code == 400


def test_upload_rejects_binary_content_claiming_to_be_csv(client, db):
    create_verified_user(db, email="binaryfile@example.com", password="Password123")
    login(client, "binaryfile@example.com", "Password123")

    resp = _upload(client, _get_csrf_headers(client), content=BINARY_FAKE_CSV)
    assert resp.status_code == 400


def test_commit_creates_dataset_and_moves_file(client, db):
    create_verified_user(db, email="commit@example.com", password="Password123")
    login(client, "commit@example.com", "Password123")

    preview_resp = _upload(client, _get_csrf_headers(client))
    body = preview_resp.get_json()

    commit_resp = client.post(
        "/datasets/upload/commit",
        data={
            "name": "Sales Test Data",
            "description": "A tiny test dataset",
            "temp_filename": body["temp_filename"],
            "original_filename": body["original_filename"],
            "file_type": body["file_type"],
            "file_size_bytes": body["file_size_bytes"],
        },
        follow_redirects=True,
    )
    assert commit_resp.status_code == 200

    dataset = Dataset.query.filter_by(name="Sales Test Data").first()
    assert dataset is not None
    assert dataset.row_count == 3
    assert dataset.column_count == 4
    assert dataset.is_cleaned_copy is False

    import os
    assert os.path.isfile(dataset.file_path)
    assert "/tmp/" not in dataset.file_path.replace("\\", "/")  # moved out of temp dir


def test_commit_without_preview_fails_gracefully(client, db):
    create_verified_user(db, email="nopreview@example.com", password="Password123")
    login(client, "nopreview@example.com", "Password123")

    resp = client.post(
        "/datasets/upload/commit",
        data={
            "name": "Ghost dataset",
            "temp_filename": "nonexistent.csv",
            "original_filename": "nonexistent.csv",
            "file_type": "csv",
            "file_size_bytes": 10,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Dataset.query.filter_by(name="Ghost dataset").first() is None


def test_dataset_list_and_detail_require_ownership(client, db):
    user_a = create_verified_user(db, email="ownera@example.com", password="Password123")
    user_b = create_verified_user(db, email="ownerb@example.com", password="Password123")

    dataset = Dataset(
        user_id=user_a.id, name="A only", file_path="/tmp/a.csv",
        original_filename="a.csv", file_type="csv", file_size_bytes=10,
        row_count=1, column_count=1,
    )
    db.session.add(dataset)
    db.session.commit()

    login(client, "ownerb@example.com", "Password123")
    resp = client.get(f"/datasets/{dataset.id}")
    assert resp.status_code == 404

    client.get("/auth/logout")
    login(client, "ownera@example.com", "Password123")
    resp_owner = client.get(f"/datasets/{dataset.id}")
    assert resp_owner.status_code == 200


def test_dataset_delete_removes_file_and_row(client, db, tmp_path):
    create_verified_user(db, email="deleter@example.com", password="Password123")
    login(client, "deleter@example.com", "Password123")

    preview_resp = _upload(client, _get_csrf_headers(client))
    body = preview_resp.get_json()
    client.post(
        "/datasets/upload/commit",
        data={
            "name": "To Delete",
            "temp_filename": body["temp_filename"],
            "original_filename": body["original_filename"],
            "file_type": body["file_type"],
            "file_size_bytes": body["file_size_bytes"],
        },
        follow_redirects=True,
    )
    dataset = Dataset.query.filter_by(name="To Delete").first()
    file_path = dataset.file_path

    import os
    assert os.path.isfile(file_path)

    resp = client.post(f"/datasets/{dataset.id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert Dataset.query.filter_by(name="To Delete").first() is None
    assert not os.path.isfile(file_path)
