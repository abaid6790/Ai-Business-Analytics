import io

from app.models import Dataset, AnalysisProject
from tests.conftest import create_verified_user, login

SAMPLE_CSV = b"region,amount\nnorth,100\nsouth,200\n"


def _upload(client, name="Project Sample"):
    data = {"file": (io.BytesIO(SAMPLE_CSV), "sample.csv")}
    resp = client.post("/datasets/upload/preview", data=data, content_type="multipart/form-data")
    body = resp.get_json()
    client.post(
        "/datasets/upload/commit",
        data={
            "name": name,
            "temp_filename": body["temp_filename"],
            "original_filename": body["original_filename"],
            "file_type": body["file_type"],
            "file_size_bytes": body["file_size_bytes"],
        },
        follow_redirects=True,
    )
    return Dataset.query.filter_by(name=name).first()


# --- Projects -----------------------------------------------------------
def test_create_and_view_project(client, db):
    create_verified_user(db, email="projowner@example.com", password="Password123")
    login(client, "projowner@example.com", "Password123")

    resp = client.post(
        "/projects/create", data={"name": "Q1 Analysis", "description": "First quarter"}, follow_redirects=True
    )
    assert resp.status_code == 200

    project = AnalysisProject.query.filter_by(name="Q1 Analysis").first()
    assert project is not None

    detail_resp = client.get(f"/projects/{project.id}")
    assert detail_resp.status_code == 200
    assert b"Q1 Analysis" in detail_resp.data


def test_create_project_requires_name(client, db):
    create_verified_user(db, email="projnoname@example.com", password="Password123")
    login(client, "projnoname@example.com", "Password123")

    resp = client.post("/projects/create", data={"name": ""}, follow_redirects=True)
    assert resp.status_code == 200
    assert AnalysisProject.query.count() == 0


def test_add_and_remove_dataset_from_project(client, db):
    create_verified_user(db, email="projassign@example.com", password="Password123")
    login(client, "projassign@example.com", "Password123")
    dataset = _upload(client)

    client.post("/projects/create", data={"name": "Assignment Test"}, follow_redirects=True)
    project = AnalysisProject.query.filter_by(name="Assignment Test").first()

    add_resp = client.post(
        f"/projects/{project.id}/add-dataset", data={"dataset_id": dataset.id}, follow_redirects=True
    )
    assert add_resp.status_code == 200
    db.session.refresh(dataset)
    assert dataset.project_id == project.id

    remove_resp = client.post(f"/projects/{project.id}/remove-dataset/{dataset.id}", follow_redirects=True)
    assert remove_resp.status_code == 200
    db.session.refresh(dataset)
    assert dataset.project_id is None


def test_delete_project_unassigns_datasets_without_deleting_them(client, db):
    create_verified_user(db, email="projdelete@example.com", password="Password123")
    login(client, "projdelete@example.com", "Password123")
    dataset = _upload(client)

    client.post("/projects/create", data={"name": "To Delete"}, follow_redirects=True)
    project = AnalysisProject.query.filter_by(name="To Delete").first()
    client.post(f"/projects/{project.id}/add-dataset", data={"dataset_id": dataset.id})

    del_resp = client.post(f"/projects/{project.id}/delete", follow_redirects=True)
    assert del_resp.status_code == 200
    assert db.session.get(AnalysisProject, project.id) is None

    # dataset itself must still exist, just unassigned
    still_there = db.session.get(Dataset, dataset.id)
    assert still_there is not None
    assert still_there.project_id is None


def test_project_isolation_across_users(client, db):
    create_verified_user(db, email="projisoowner@example.com", password="Password123")
    login(client, "projisoowner@example.com", "Password123")
    client.post("/projects/create", data={"name": "Private Project"}, follow_redirects=True)
    project = AnalysisProject.query.filter_by(name="Private Project").first()
    client.get("/auth/logout")

    create_verified_user(db, email="projisointruder@example.com", password="Password123")
    login(client, "projisointruder@example.com", "Password123")

    assert client.get(f"/projects/{project.id}").status_code == 404
    assert client.post(f"/projects/{project.id}/delete").status_code == 404


def test_project_edit_updates_name(client, db):
    create_verified_user(db, email="projedit@example.com", password="Password123")
    login(client, "projedit@example.com", "Password123")
    client.post("/projects/create", data={"name": "Old Name"}, follow_redirects=True)
    project = AnalysisProject.query.filter_by(name="Old Name").first()

    resp = client.post(f"/projects/{project.id}/edit", data={"name": "New Name"}, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(project)
    assert project.name == "New Name"


# --- History --------------------------------------------------------------
def test_history_page_shows_logged_activity(client, db):
    create_verified_user(db, email="historyuser@example.com", password="Password123")
    login(client, "historyuser@example.com", "Password123")
    _upload(client, name="History Trigger")

    resp = client.get("/history/")
    assert resp.status_code == 200
    assert b"Dataset Upload" in resp.data or b"dataset upload" in resp.data.lower()


def test_history_isolated_per_user(client, db):
    create_verified_user(db, email="historyowner@example.com", password="Password123")
    login(client, "historyowner@example.com", "Password123")
    _upload(client, name="Owner Dataset")
    client.get("/auth/logout")

    create_verified_user(db, email="historyother@example.com", password="Password123")
    login(client, "historyother@example.com", "Password123")

    resp = client.get("/history/")
    assert b"Owner Dataset" not in resp.data
