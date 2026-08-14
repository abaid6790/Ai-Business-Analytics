import io
import json

from app.models import Dataset, Report
from tests.conftest import create_verified_user, login

SAMPLE_CSV = (
    b"region,amount\n"
    b"north,100\nsouth,200\nnorth,150\nsouth,50\neast,300\n"
)


def _upload(client, name="Report Sample"):
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


def test_report_builder_page_loads(client, db):
    create_verified_user(db, email="reportbuilder@example.com", password="Password123")
    login(client, "reportbuilder@example.com", "Password123")
    dataset = _upload(client)

    resp = client.get(f"/reports/build/{dataset.id}")
    assert resp.status_code == 200


def test_generate_pdf_report(client, db):
    create_verified_user(db, email="reportpdf@example.com", password="Password123")
    login(client, "reportpdf@example.com", "Password123")
    dataset = _upload(client)

    resp = client.post(
        f"/reports/build/{dataset.id}",
        data={"format": "pdf", "title": "My PDF Report"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    report = Report.query.filter_by(title="My PDF Report").first()
    assert report is not None
    assert report.format == "pdf"

    import os
    assert os.path.isfile(report.file_path)


def test_generate_all_formats(client, db):
    create_verified_user(db, email="reportformats@example.com", password="Password123")
    login(client, "reportformats@example.com", "Password123")
    dataset = _upload(client)

    for fmt in ("pdf", "xlsx", "csv", "json"):
        resp = client.post(
            f"/reports/build/{dataset.id}",
            data={"format": fmt, "title": f"Report {fmt}"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        report = Report.query.filter_by(title=f"Report {fmt}").first()
        assert report is not None
        assert report.format == fmt


def test_report_download(client, db):
    create_verified_user(db, email="reportdownload@example.com", password="Password123")
    login(client, "reportdownload@example.com", "Password123")
    dataset = _upload(client)

    client.post(f"/reports/build/{dataset.id}", data={"format": "json", "title": "Downloadable"}, follow_redirects=True)
    report = Report.query.filter_by(title="Downloadable").first()

    resp = client.get(f"/reports/{report.id}/download")
    assert resp.status_code == 200


def test_report_delete_removes_file_and_row(client, db):
    create_verified_user(db, email="reportdelete@example.com", password="Password123")
    login(client, "reportdelete@example.com", "Password123")
    dataset = _upload(client)

    client.post(f"/reports/build/{dataset.id}", data={"format": "json", "title": "ToDelete"}, follow_redirects=True)
    report = Report.query.filter_by(title="ToDelete").first()
    file_path = report.file_path

    import os
    assert os.path.isfile(file_path)

    resp = client.post(f"/reports/{report.id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert db.session.get(Report, report.id) is None
    assert not os.path.isfile(file_path)


def test_reports_list_shows_generated_reports(client, db):
    create_verified_user(db, email="reportlist@example.com", password="Password123")
    login(client, "reportlist@example.com", "Password123")
    dataset = _upload(client)

    client.post(f"/reports/build/{dataset.id}", data={"format": "json", "title": "Listed Report"}, follow_redirects=True)
    resp = client.get("/reports/")
    assert resp.status_code == 200
    assert b"Listed Report" in resp.data


def test_report_generation_isolation_across_users(client, db):
    create_verified_user(db, email="reportowner@example.com", password="Password123")
    login(client, "reportowner@example.com", "Password123")
    dataset = _upload(client)
    client.post(f"/reports/build/{dataset.id}", data={"format": "json", "title": "Private Report"}, follow_redirects=True)
    report = Report.query.filter_by(title="Private Report").first()
    client.get("/auth/logout")

    create_verified_user(db, email="reportintruder@example.com", password="Password123")
    login(client, "reportintruder@example.com", "Password123")

    assert client.get(f"/reports/build/{dataset.id}").status_code == 404
    assert client.post(f"/reports/build/{dataset.id}", data={"format": "json"}).status_code == 404
    assert client.get(f"/reports/{report.id}/download").status_code == 404
    assert client.post(f"/reports/{report.id}/delete").status_code == 404


def test_generate_report_rejects_invalid_format(client, db):
    create_verified_user(db, email="reportbadfmt@example.com", password="Password123")
    login(client, "reportbadfmt@example.com", "Password123")
    dataset = _upload(client)

    resp = client.post(
        f"/reports/build/{dataset.id}",
        data={"format": "docx", "title": "Bad Format"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Report.query.filter_by(title="Bad Format").first() is None
