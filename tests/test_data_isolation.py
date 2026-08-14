from flask import Blueprint
from flask_login import login_required

from app.models import Dataset
from app.utils.ownership import get_owned_or_404, owner_scoped_query
from tests.conftest import create_verified_user, login


def _make_probe_blueprint():
    """
    A tiny throwaway blueprint that exercises get_owned_or_404 /
    owner_scoped_query directly, so isolation is tested at the utility
    level (not just indirectly through not-yet-built dataset routes).
    """
    bp = Blueprint("probe", __name__)

    @bp.route("/probe/dataset/<int:dataset_id>")
    @login_required
    def get_dataset(dataset_id):
        dataset = get_owned_or_404(Dataset, dataset_id)
        return {"id": dataset.id, "name": dataset.name}

    @bp.route("/probe/datasets")
    @login_required
    def list_datasets():
        rows = owner_scoped_query(Dataset).all()
        return {"count": len(rows)}

    return bp


def test_user_cannot_access_another_users_dataset(app, client, db):
    app.register_blueprint(_make_probe_blueprint())

    user_a = create_verified_user(db, email="a-owner@example.com", password="Password123")
    user_b = create_verified_user(db, email="b-owner@example.com", password="Password123")

    dataset = Dataset(
        user_id=user_a.id,
        name="A's private data",
        file_path="/tmp/a.csv",
        original_filename="a.csv",
        file_type="csv",
        file_size_bytes=100,
    )
    db.session.add(dataset)
    db.session.commit()

    # User B logs in and tries to access User A's dataset by ID.
    login(client, "b-owner@example.com", "Password123")
    resp = client.get(f"/probe/dataset/{dataset.id}")
    assert resp.status_code == 404  # not 403 — existence isn't leaked either

    client.get("/auth/logout")

    # User A can access their own dataset just fine.
    login(client, "a-owner@example.com", "Password123")
    resp_owner = client.get(f"/probe/dataset/{dataset.id}")
    assert resp_owner.status_code == 200
    assert resp_owner.get_json()["name"] == "A's private data"


def test_owner_scoped_query_only_returns_own_rows(app, client, db):
    app.register_blueprint(_make_probe_blueprint())

    user_a = create_verified_user(db, email="scoped-a@example.com", password="Password123")
    user_b = create_verified_user(db, email="scoped-b@example.com", password="Password123")

    for i in range(3):
        db.session.add(Dataset(
            user_id=user_a.id, name=f"A{i}", file_path=f"/tmp/a{i}.csv",
            original_filename=f"a{i}.csv", file_type="csv", file_size_bytes=10,
        ))
    for i in range(2):
        db.session.add(Dataset(
            user_id=user_b.id, name=f"B{i}", file_path=f"/tmp/b{i}.csv",
            original_filename=f"b{i}.csv", file_type="csv", file_size_bytes=10,
        ))
    db.session.commit()

    login(client, "scoped-b@example.com", "Password123")
    resp = client.get("/probe/datasets")
    assert resp.get_json()["count"] == 2  # only B's rows, never A's
