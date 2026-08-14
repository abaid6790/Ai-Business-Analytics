import io
import json

from app.models import Dataset, Chart
from tests.conftest import create_verified_user, login

SAMPLE_CSV = (
    b"category,amount,region,signup_date\n"
    b"a,10,north,2024-01-01\n"
    b"b,20,south,2024-01-02\n"
    b"a,15,north,2024-01-03\n"
    b"b,25,south,2024-01-04\n"
    b"a,12,north,2024-01-05\n"
    b"c,100,east,2024-01-06\n"
)


def _upload_sample_dataset(client, name="Sample Data"):
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


def test_eda_page_loads(client, db):
    create_verified_user(db, email="edauser@example.com", password="Password123")
    login(client, "edauser@example.com", "Password123")
    dataset = _upload_sample_dataset(client)

    resp = client.get(f"/analytics/{dataset.id}/eda")
    assert resp.status_code == 200


def test_eda_data_endpoint_returns_stats_and_charts(client, db):
    create_verified_user(db, email="edadata@example.com", password="Password123")
    login(client, "edadata@example.com", "Password123")
    dataset = _upload_sample_dataset(client)

    resp = client.get(f"/analytics/{dataset.id}/eda/data")
    assert resp.status_code == 200
    body = resp.get_json()

    assert "amount" in body["stats"]["numeric"]
    assert "category" in body["stats"]["categorical"]
    assert len(body["charts"]) > 0
    assert "correlation" in body


def test_eda_requires_ownership(client, db):
    create_verified_user(db, email="edaowner@example.com", password="Password123")
    login(client, "edaowner@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    client.get("/auth/logout")

    create_verified_user(db, email="edaintruder@example.com", password="Password123")
    login(client, "edaintruder@example.com", "Password123")

    resp = client.get(f"/analytics/{dataset.id}/eda/data")
    assert resp.status_code == 404


def test_chart_builder_page_loads(client, db):
    create_verified_user(db, email="builderuser@example.com", password="Password123")
    login(client, "builderuser@example.com", "Password123")
    dataset = _upload_sample_dataset(client)

    resp = client.get(f"/analytics/{dataset.id}/charts/builder")
    assert resp.status_code == 200
    assert b"category" in resp.data


def test_chart_preview_endpoint(client, db):
    create_verified_user(db, email="previewuser@example.com", password="Password123")
    login(client, "previewuser@example.com", "Password123")
    dataset = _upload_sample_dataset(client)

    resp = client.post(
        f"/analytics/{dataset.id}/charts/preview",
        data=json.dumps({"chart_type": "bar", "x": "category", "y": "amount", "aggregation": "sum"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["chart_type"] == "bar"


def test_chart_preview_invalid_spec_returns_error(client, db):
    create_verified_user(db, email="badpreview@example.com", password="Password123")
    login(client, "badpreview@example.com", "Password123")
    dataset = _upload_sample_dataset(client)

    resp = client.post(
        f"/analytics/{dataset.id}/charts/preview",
        data=json.dumps({"chart_type": "bar", "x": "does_not_exist"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_save_chart_creates_record_and_view_renders(client, db):
    create_verified_user(db, email="savechart@example.com", password="Password123")
    login(client, "savechart@example.com", "Password123")
    dataset = _upload_sample_dataset(client)

    config = {"chart_type": "bar", "x": "category", "y": "amount", "aggregation": "sum"}
    resp = client.post(
        f"/analytics/{dataset.id}/charts",
        data={
            "title": "Amount by Category",
            "chart_type": "bar",
            "config_json": json.dumps(config),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    chart = Chart.query.filter_by(title="Amount by Category").first()
    assert chart is not None
    assert chart.dataset_id == dataset.id

    view_resp = client.get(f"/analytics/charts/{chart.id}")
    assert view_resp.status_code == 200
    assert b"Amount by Category" in view_resp.data


def test_chart_list_shows_saved_charts(client, db):
    create_verified_user(db, email="chartlist@example.com", password="Password123")
    login(client, "chartlist@example.com", "Password123")
    dataset = _upload_sample_dataset(client)

    config = {"chart_type": "bar", "x": "category"}
    client.post(
        f"/analytics/{dataset.id}/charts",
        data={"title": "My Chart", "chart_type": "bar", "config_json": json.dumps(config)},
        follow_redirects=True,
    )

    resp = client.get(f"/analytics/charts/list/{dataset.id}")
    assert resp.status_code == 200
    assert b"My Chart" in resp.data


def test_delete_chart_removes_record(client, db):
    create_verified_user(db, email="deletechart@example.com", password="Password123")
    login(client, "deletechart@example.com", "Password123")
    dataset = _upload_sample_dataset(client)

    config = {"chart_type": "bar", "x": "category"}
    client.post(
        f"/analytics/{dataset.id}/charts",
        data={"title": "Delete Me", "chart_type": "bar", "config_json": json.dumps(config)},
        follow_redirects=True,
    )
    chart = Chart.query.filter_by(title="Delete Me").first()

    resp = client.post(f"/analytics/charts/{chart.id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert db.session.get(Chart, chart.id) is None


def test_chart_isolation_across_users(client, db):
    create_verified_user(db, email="chartowner@example.com", password="Password123")
    login(client, "chartowner@example.com", "Password123")
    dataset = _upload_sample_dataset(client)

    config = {"chart_type": "bar", "x": "category"}
    client.post(
        f"/analytics/{dataset.id}/charts",
        data={"title": "Private Chart", "chart_type": "bar", "config_json": json.dumps(config)},
        follow_redirects=True,
    )
    chart = Chart.query.filter_by(title="Private Chart").first()
    client.get("/auth/logout")

    create_verified_user(db, email="chartintruder@example.com", password="Password123")
    login(client, "chartintruder@example.com", "Password123")

    resp = client.get(f"/analytics/charts/{chart.id}")
    assert resp.status_code == 404

    resp2 = client.post(f"/analytics/charts/{chart.id}/delete")
    assert resp2.status_code == 404

    client.get("/auth/logout")
    login(client, "chartowner@example.com", "Password123")
    assert db.session.get(Chart, chart.id) is not None
