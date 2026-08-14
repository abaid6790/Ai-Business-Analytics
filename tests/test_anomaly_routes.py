import io
import json

from app.models import Dataset
from tests.conftest import create_verified_user, login

ANOMALY_CSV = (
    b"amount,region\n"
    b"10,north\n11,south\n12,north\n13,south\n10,north\n"
    b"11,south\n12,north\n13,south\n10,north\n1000,south\n"
)


def _upload_anomaly_dataset(client, name="Anomaly Sample"):
    data = {"file": (io.BytesIO(ANOMALY_CSV), "anomaly.csv")}
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


def test_anomaly_page_loads(client, db):
    create_verified_user(db, email="anomalypage@example.com", password="Password123")
    login(client, "anomalypage@example.com", "Password123")
    dataset = _upload_anomaly_dataset(client)

    resp = client.get(f"/anomaly/{dataset.id}")
    assert resp.status_code == 200
    assert b"amount" in resp.data


def test_anomaly_detect_iqr(client, db):
    create_verified_user(db, email="detectiqr@example.com", password="Password123")
    login(client, "detectiqr@example.com", "Password123")
    dataset = _upload_anomaly_dataset(client)

    resp = client.post(
        f"/anomaly/{dataset.id}/detect",
        data=json.dumps({"method": "iqr", "columns": ["amount"]}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["anomaly_count"] >= 1
    flagged = [a["row"]["amount"] for a in body["anomalies"]]
    assert 1000 in flagged


def test_anomaly_detect_zscore(client, db):
    create_verified_user(db, email="detectz@example.com", password="Password123")
    login(client, "detectz@example.com", "Password123")
    dataset = _upload_anomaly_dataset(client)

    resp = client.post(
        f"/anomaly/{dataset.id}/detect",
        data=json.dumps({"method": "zscore", "columns": ["amount"], "threshold": 1.0}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["threshold"] == 1.0


def test_anomaly_detect_isolation_forest(client, db):
    create_verified_user(db, email="detectif@example.com", password="Password123")
    login(client, "detectif@example.com", "Password123")
    dataset = _upload_anomaly_dataset(client)

    resp = client.post(
        f"/anomaly/{dataset.id}/detect",
        data=json.dumps({"method": "isolation_forest", "columns": ["amount"], "contamination": 0.2}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["method"] == "isolation_forest"


def test_anomaly_detect_rejects_no_columns(client, db):
    create_verified_user(db, email="nocolumns@example.com", password="Password123")
    login(client, "nocolumns@example.com", "Password123")
    dataset = _upload_anomaly_dataset(client)

    resp = client.post(
        f"/anomaly/{dataset.id}/detect",
        data=json.dumps({"method": "iqr", "columns": []}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_anomaly_detect_rejects_non_numeric_column(client, db):
    create_verified_user(db, email="nonnumeric@example.com", password="Password123")
    login(client, "nonnumeric@example.com", "Password123")
    dataset = _upload_anomaly_dataset(client)

    resp = client.post(
        f"/anomaly/{dataset.id}/detect",
        data=json.dumps({"method": "iqr", "columns": ["region"]}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_anomaly_isolation_across_users(client, db):
    create_verified_user(db, email="anomalyowner@example.com", password="Password123")
    login(client, "anomalyowner@example.com", "Password123")
    dataset = _upload_anomaly_dataset(client)
    client.get("/auth/logout")

    create_verified_user(db, email="anomalyintruder@example.com", password="Password123")
    login(client, "anomalyintruder@example.com", "Password123")

    resp = client.get(f"/anomaly/{dataset.id}")
    assert resp.status_code == 404

    resp2 = client.post(
        f"/anomaly/{dataset.id}/detect",
        data=json.dumps({"method": "iqr", "columns": ["amount"]}),
        content_type="application/json",
    )
    assert resp2.status_code == 404
