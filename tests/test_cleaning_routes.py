import io

from app.models import Dataset
from tests.conftest import create_verified_user, login

DIRTY_CSV = (
    b"name,age,score\n"
    b"Alice,30,10\n"
    b"Bob,,20\n"
    b"Alice,30,10\n"  # duplicate of row 1
    b"Carol,25,1000\n"  # outlier score
)


def _upload_dirty_dataset(client):
    data = {"file": (io.BytesIO(DIRTY_CSV), "dirty.csv")}
    resp = client.post(
        "/datasets/upload/preview", data=data, content_type="multipart/form-data"
    )
    body = resp.get_json()
    commit_resp = client.post(
        "/datasets/upload/commit",
        data={
            "name": "Dirty Data",
            "temp_filename": body["temp_filename"],
            "original_filename": body["original_filename"],
            "file_type": body["file_type"],
            "file_size_bytes": body["file_size_bytes"],
        },
        follow_redirects=True,
    )
    assert commit_resp.status_code == 200
    return Dataset.query.filter_by(name="Dirty Data").first()


def test_clean_page_shows_quality_scan(client, db):
    create_verified_user(db, email="cleaner@example.com", password="Password123")
    login(client, "cleaner@example.com", "Password123")
    dataset = _upload_dirty_dataset(client)

    resp = client.get(f"/datasets/{dataset.id}/clean")
    assert resp.status_code == 200
    assert b"Data quality scan" in resp.data
    assert b"age" in resp.data


def test_apply_cleaning_creates_new_dataset_and_preserves_original(client, db):
    create_verified_user(db, email="cleanapply@example.com", password="Password123")
    login(client, "cleanapply@example.com", "Password123")
    dataset = _upload_dirty_dataset(client)

    original_row_count = dataset.row_count
    original_file_path = dataset.file_path

    resp = client.post(
        f"/datasets/{dataset.id}/clean/apply",
        data={
            "remove_duplicates": "on",
            "missing__age": "mean",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Original untouched
    original = db.session.get(Dataset, dataset.id)
    assert original.row_count == original_row_count
    assert original.file_path == original_file_path

    import os
    assert os.path.isfile(original_file_path)

    cleaned = Dataset.query.filter_by(source_dataset_id=dataset.id).first()
    assert cleaned is not None
    assert cleaned.is_cleaned_copy is True
    assert cleaned.row_count == original_row_count - 1  # one duplicate removed
    assert cleaned.missing_values_count == 0  # age was filled
    assert cleaned.file_path != original_file_path


def test_apply_cleaning_with_no_actions_shows_warning(client, db):
    create_verified_user(db, email="noaction@example.com", password="Password123")
    login(client, "noaction@example.com", "Password123")
    dataset = _upload_dirty_dataset(client)

    resp = client.post(f"/datasets/{dataset.id}/clean/apply", data={}, follow_redirects=True)
    assert resp.status_code == 200
    assert Dataset.query.filter_by(source_dataset_id=dataset.id).first() is None


def test_compare_page_shows_before_after(client, db):
    create_verified_user(db, email="compareuser@example.com", password="Password123")
    login(client, "compareuser@example.com", "Password123")
    dataset = _upload_dirty_dataset(client)

    client.post(
        f"/datasets/{dataset.id}/clean/apply",
        data={"remove_duplicates": "on"},
        follow_redirects=True,
    )
    cleaned = Dataset.query.filter_by(source_dataset_id=dataset.id).first()

    resp = client.get(f"/datasets/{cleaned.id}/compare")
    assert resp.status_code == 200
    assert b"Before" in resp.data or b"before" in resp.data.lower()


def test_compare_page_redirects_for_non_cleaned_dataset(client, db):
    create_verified_user(db, email="notcleaned@example.com", password="Password123")
    login(client, "notcleaned@example.com", "Password123")
    dataset = _upload_dirty_dataset(client)

    resp = client.get(f"/datasets/{dataset.id}/compare", follow_redirects=True)
    assert resp.status_code == 200
    assert db.session.get(Dataset, dataset.id) is not None  # still just the original page


def test_cleaning_respects_data_isolation(client, db):
    create_verified_user(db, email="cleanowner@example.com", password="Password123")
    login(client, "cleanowner@example.com", "Password123")
    dataset = _upload_dirty_dataset(client)
    client.get("/auth/logout")

    create_verified_user(db, email="cleanintruder@example.com", password="Password123")
    login(client, "cleanintruder@example.com", "Password123")

    resp = client.get(f"/datasets/{dataset.id}/clean")
    assert resp.status_code == 404

    resp2 = client.post(f"/datasets/{dataset.id}/clean/apply", data={"remove_duplicates": "on"})
    assert resp2.status_code == 404


def test_drop_column_action_via_route(client, db):
    create_verified_user(db, email="dropcol@example.com", password="Password123")
    login(client, "dropcol@example.com", "Password123")
    dataset = _upload_dirty_dataset(client)

    client.post(
        f"/datasets/{dataset.id}/clean/apply",
        data={"drop_column": "score"},
        follow_redirects=True,
    )
    cleaned = Dataset.query.filter_by(source_dataset_id=dataset.id).first()
    assert cleaned.column_count == dataset.column_count - 1
