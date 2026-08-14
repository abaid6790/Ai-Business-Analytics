import pytest

from app import create_app
from app.extensions import db as _db
from config import TestingConfig
from app.models import User
from app.utils.tokens import generate_token


@pytest.fixture()
def app():
    application = create_app(TestingConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    return _db


def create_verified_user(db, email="user@example.com", password="Password123", full_name="Test User"):
    user = User(email=email, full_name=full_name, is_email_verified=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def create_unverified_user(db, email="unverified@example.com", password="Password123"):
    user = User(email=email, full_name="Unverified User", is_email_verified=False)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def login(client, email, password, remember=False):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password, "remember_me": remember},
        follow_redirects=True,
    )
