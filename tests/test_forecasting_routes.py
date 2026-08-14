import io
import json
import math

from app.models import Dataset
from tests.conftest import create_verified_user, login


def _seasonal_csv(n=36):
    rows = ["date,revenue"]
    for i in range(n):
        year = 2021 + i // 12
        month = (i % 12) + 1
        trend = i * 50
        seasonal = 200 * math.sin(i * 2 * math.pi / 12)
        value = 1000 + trend + seasonal
        rows.append(f"{year}-{month:02d}-01,{value:.2f}")
    return ("\n".join(rows) + "\n").encode()


def _no_date_csv():
    return b"category,amount\na,10\nb,20\nc,30\n"


def _upload(client, csv_bytes, name):
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


def test_forecasting_page_loads_with_eligible_dataset(client, db):
    create_verified_user(db, email="fcstpage@example.com", password="Password123")
    login(client, "fcstpage@example.com", "Password123")
    dataset = _upload(client, _seasonal_csv(), "Seasonal Sample")

    resp = client.get(f"/forecasting/{dataset.id}")
    assert resp.status_code == 200
    assert b"date" in resp.data


def test_forecasting_page_shows_empty_state_for_ineligible_dataset(client, db):
    create_verified_user(db, email="fcstineligible@example.com", password="Password123")
    login(client, "fcstineligible@example.com", "Password123")
    dataset = _upload(client, _no_date_csv(), "No Date Sample")

    resp = client.get(f"/forecasting/{dataset.id}")
    assert resp.status_code == 200
    assert b"not available" in resp.data.lower()


def test_dataset_detail_hides_forecast_button_when_ineligible(client, db):
    create_verified_user(db, email="fcsthide@example.com", password="Password123")
    login(client, "fcsthide@example.com", "Password123")
    dataset = _upload(client, _no_date_csv(), "Hide Forecast Sample")

    resp = client.get(f"/datasets/{dataset.id}")
    assert f"/forecasting/{dataset.id}".encode() not in resp.data


def test_dataset_detail_shows_forecast_button_when_eligible(client, db):
    create_verified_user(db, email="fcstshow@example.com", password="Password123")
    login(client, "fcstshow@example.com", "Password123")
    dataset = _upload(client, _seasonal_csv(), "Show Forecast Sample")

    resp = client.get(f"/datasets/{dataset.id}")
    assert f"/forecasting/{dataset.id}".encode() in resp.data


def test_generate_forecast_returns_full_result(client, db):
    create_verified_user(db, email="fcstgen@example.com", password="Password123")
    login(client, "fcstgen@example.com", "Password123")
    dataset = _upload(client, _seasonal_csv(), "Generate Forecast Sample")

    resp = client.post(
        f"/forecasting/{dataset.id}/generate",
        data=json.dumps({"date_column": "date", "value_column": "revenue", "periods": 6}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["forecast"]) == 6
    assert body["method"] in ("holt_winters_seasonal", "holt_linear_trend")
    assert body["trend"]["direction"] == "increasing"


def test_generate_forecast_rejects_missing_columns(client, db):
    create_verified_user(db, email="fcstmissing@example.com", password="Password123")
    login(client, "fcstmissing@example.com", "Password123")
    dataset = _upload(client, _seasonal_csv(), "Missing Columns Sample")

    resp = client.post(
        f"/forecasting/{dataset.id}/generate",
        data=json.dumps({"date_column": "", "value_column": "revenue"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_generate_forecast_rejects_invalid_column_name(client, db):
    create_verified_user(db, email="fcstbadcol@example.com", password="Password123")
    login(client, "fcstbadcol@example.com", "Password123")
    dataset = _upload(client, _seasonal_csv(), "Bad Column Sample")

    resp = client.post(
        f"/forecasting/{dataset.id}/generate",
        data=json.dumps({"date_column": "date", "value_column": "nonexistent"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_forecasting_isolation_across_users(client, db):
    create_verified_user(db, email="fcstowner@example.com", password="Password123")
    login(client, "fcstowner@example.com", "Password123")
    dataset = _upload(client, _seasonal_csv(), "Isolation Sample")
    client.get("/auth/logout")

    create_verified_user(db, email="fcstintruder@example.com", password="Password123")
    login(client, "fcstintruder@example.com", "Password123")

    assert client.get(f"/forecasting/{dataset.id}").status_code == 404
    resp = client.post(
        f"/forecasting/{dataset.id}/generate",
        data=json.dumps({"date_column": "date", "value_column": "revenue"}),
        content_type="application/json",
    )
    assert resp.status_code == 404
