import io
import json
import time

from app.models import Dataset, MLModel
from tests.conftest import create_verified_user, login

CLASSIFICATION_CSV_HEADER = "score,age,segment,target\n"


def _classification_csv(n=120):
    import random
    random.seed(0)
    rows = [CLASSIFICATION_CSV_HEADER]
    for i in range(n):
        score = random.gauss(50, 10)
        age = random.randint(18, 65)
        segment = random.choice(["a", "b", "c"])
        target = 1 if score > 50 else 0
        rows.append(f"{score:.2f},{age},{segment},{target}\n")
    return "".join(rows).encode()


def _upload_dataset(client, csv_bytes, name):
    data = {"file": (io.BytesIO(csv_bytes), "data.csv")}
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


def _wait_for_training(client, dataset_id, training_run_id, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/ml/{dataset_id}/status?training_run_id={training_run_id}")
        models = resp.get_json()["models"]
        if models and all(m["status"] in ("completed", "failed") for m in models):
            return models
        time.sleep(0.5)
    raise TimeoutError("Training did not complete in time")


def test_ml_index_page_loads(client, db):
    create_verified_user(db, email="mlpage@example.com", password="Password123")
    login(client, "mlpage@example.com", "Password123")
    dataset = _upload_dataset(client, _classification_csv(), "ML Sample")

    resp = client.get(f"/ml/{dataset.id}")
    assert resp.status_code == 200
    assert b"target" in resp.data


def test_full_training_run_completes_and_ranks_best_model(client, db, app):
    create_verified_user(db, email="mltrain@example.com", password="Password123")
    login(client, "mltrain@example.com", "Password123")
    dataset = _upload_dataset(client, _classification_csv(), "ML Train Sample")

    resp = client.post(
        f"/ml/{dataset.id}/train",
        data=json.dumps({"target_column": "target", "feature_columns": ["score", "age", "segment"]}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["task_type"] == "classification"
    assert len(body["model_ids"]) == 5  # 5 classification algorithms

    models = _wait_for_training(client, dataset.id, body["training_run_id"])
    assert all(m["status"] == "completed" for m in models), models

    best_count = sum(1 for m in models if m["is_best_model"])
    assert best_count == 1

    for m in models:
        assert m["metrics"]["accuracy"] > 0.6  # should have learned the real signal


def test_train_rejects_invalid_target_column(client, db):
    create_verified_user(db, email="badtarget@example.com", password="Password123")
    login(client, "badtarget@example.com", "Password123")
    dataset = _upload_dataset(client, _classification_csv(), "Bad Target Sample")

    resp = client.post(
        f"/ml/{dataset.id}/train",
        data=json.dumps({"target_column": "nonexistent"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_train_defaults_to_all_other_columns_as_features(client, db):
    create_verified_user(db, email="defaultfeat@example.com", password="Password123")
    login(client, "defaultfeat@example.com", "Password123")
    dataset = _upload_dataset(client, _classification_csv(), "Default Features Sample")

    resp = client.post(
        f"/ml/{dataset.id}/train",
        data=json.dumps({"target_column": "target"}),  # no feature_columns given
        content_type="application/json",
    )
    assert resp.status_code == 200


def test_model_detail_and_predict_after_training(client, db, app):
    create_verified_user(db, email="mldetail@example.com", password="Password123")
    login(client, "mldetail@example.com", "Password123")
    dataset = _upload_dataset(client, _classification_csv(), "ML Detail Sample")

    resp = client.post(
        f"/ml/{dataset.id}/train",
        data=json.dumps({"target_column": "target", "feature_columns": ["score", "age", "segment"]}),
        content_type="application/json",
    )
    body = resp.get_json()
    _wait_for_training(client, dataset.id, body["training_run_id"])

    best_model = MLModel.query.filter_by(dataset_id=dataset.id, is_best_model=True).first()
    assert best_model is not None

    detail_resp = client.get(f"/ml/models/{best_model.id}")
    assert detail_resp.status_code == 200
    assert b"Feature importance" in detail_resp.data

    predict_resp = client.post(
        f"/ml/models/{best_model.id}/predict",
        data=json.dumps({"score": "60", "age": "30", "segment": "a"}),
        content_type="application/json",
    )
    assert predict_resp.status_code == 200
    predict_body = predict_resp.get_json()
    assert predict_body["prediction"] in (0, 1)


def test_predict_rejects_missing_features(client, db, app):
    create_verified_user(db, email="predictmissing@example.com", password="Password123")
    login(client, "predictmissing@example.com", "Password123")
    dataset = _upload_dataset(client, _classification_csv(), "Predict Missing Sample")

    resp = client.post(
        f"/ml/{dataset.id}/train",
        data=json.dumps({"target_column": "target", "feature_columns": ["score", "age", "segment"]}),
        content_type="application/json",
    )
    body = resp.get_json()
    _wait_for_training(client, dataset.id, body["training_run_id"])

    best_model = MLModel.query.filter_by(dataset_id=dataset.id, is_best_model=True).first()
    predict_resp = client.post(
        f"/ml/models/{best_model.id}/predict",
        data=json.dumps({"score": "60"}),  # missing age, segment
        content_type="application/json",
    )
    assert predict_resp.status_code == 400


def test_model_delete_removes_file_and_row(client, db, app):
    create_verified_user(db, email="mldelete@example.com", password="Password123")
    login(client, "mldelete@example.com", "Password123")
    dataset = _upload_dataset(client, _classification_csv(), "ML Delete Sample")

    resp = client.post(
        f"/ml/{dataset.id}/train",
        data=json.dumps({"target_column": "target", "feature_columns": ["score", "age", "segment"]}),
        content_type="application/json",
    )
    body = resp.get_json()
    _wait_for_training(client, dataset.id, body["training_run_id"])

    model = MLModel.query.filter_by(dataset_id=dataset.id).first()
    model_path = model.model_file_path

    import os
    assert os.path.isfile(model_path)

    del_resp = client.post(f"/ml/models/{model.id}/delete", follow_redirects=True)
    assert del_resp.status_code == 200
    assert db.session.get(MLModel, model.id) is None
    assert not os.path.isfile(model_path)


def test_ml_isolation_across_users(client, db, app):
    create_verified_user(db, email="mlowner@example.com", password="Password123")
    login(client, "mlowner@example.com", "Password123")
    dataset = _upload_dataset(client, _classification_csv(), "ML Isolation Sample")

    resp = client.post(
        f"/ml/{dataset.id}/train",
        data=json.dumps({"target_column": "target", "feature_columns": ["score", "age", "segment"]}),
        content_type="application/json",
    )
    body = resp.get_json()
    _wait_for_training(client, dataset.id, body["training_run_id"])
    model = MLModel.query.filter_by(dataset_id=dataset.id).first()
    client.get("/auth/logout")

    create_verified_user(db, email="mlintruder@example.com", password="Password123")
    login(client, "mlintruder@example.com", "Password123")

    assert client.get(f"/ml/{dataset.id}").status_code == 404
    assert client.get(f"/ml/models/{model.id}").status_code == 404
    assert client.post(
        f"/ml/{dataset.id}/train", data=json.dumps({"target_column": "target"}), content_type="application/json"
    ).status_code == 404
