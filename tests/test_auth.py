import re

from app.models import User, EmailVerification
from tests.conftest import create_verified_user, create_unverified_user, login


def _extract_verify_token_from_log(caplog):
    """The dev mail backend logs the email body; pull the token out of the URL."""
    for record in caplog.records:
        match = re.search(r"/auth/verify-email/([\w\-.]+)", record.message)
        if match:
            return match.group(1)
    return None


def test_register_creates_unverified_user(client, db, caplog):
    caplog.set_level("INFO")
    resp = client.post(
        "/auth/register",
        data={
            "full_name": "New User",
            "email": "newuser@example.com",
            "password": "Password123",
            "confirm_password": "Password123",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    user = User.query.filter_by(email="newuser@example.com").first()
    assert user is not None
    assert user.is_email_verified is False
    assert user.check_password("Password123") is True


def test_register_rejects_duplicate_email(client, db):
    create_verified_user(db, email="dupe@example.com")

    resp = client.post(
        "/auth/register",
        data={
            "full_name": "Dupe",
            "email": "dupe@example.com",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    assert b"already exists" in resp.data


def test_register_rejects_mismatched_passwords(client, db):
    resp = client.post(
        "/auth/register",
        data={
            "full_name": "X",
            "email": "x@example.com",
            "password": "Password123",
            "confirm_password": "Different123",
        },
    )
    assert User.query.filter_by(email="x@example.com").first() is None


def test_email_verification_flow(client, db, caplog):
    caplog.set_level("INFO")
    client.post(
        "/auth/register",
        data={
            "full_name": "Verify Me",
            "email": "verifyme@example.com",
            "password": "Password123",
            "confirm_password": "Password123",
        },
    )
    user = User.query.filter_by(email="verifyme@example.com").first()
    assert user.is_email_verified is False

    record = EmailVerification.query.filter_by(user_id=user.id).first()
    resp = client.get(f"/auth/verify-email/{record.token}", follow_redirects=True)
    assert resp.status_code == 200

    db.session.refresh(user)
    assert user.is_email_verified is True

    # Reusing the same token should not blow up, just inform the user.
    resp2 = client.get(f"/auth/verify-email/{record.token}", follow_redirects=True)
    assert resp2.status_code == 200


def test_login_blocked_until_email_verified(client, db):
    create_unverified_user(db, email="notverified@example.com")
    resp = login(client, "notverified@example.com", "Password123")
    assert b"verify your email" in resp.data.lower()


def test_login_success_and_logout(client, db):
    create_verified_user(db, email="loginok@example.com", password="Password123")
    resp = login(client, "loginok@example.com", "Password123")
    assert resp.status_code == 200

    dash_resp = client.get("/dashboard/", follow_redirects=True)
    assert dash_resp.status_code == 200

    logout_resp = client.get("/auth/logout", follow_redirects=True)
    assert logout_resp.status_code == 200

    # After logout, dashboard should redirect to login
    post_logout = client.get("/dashboard/", follow_redirects=False)
    assert post_logout.status_code in (302, 401, 403)


def test_login_wrong_password_fails(client, db):
    create_verified_user(db, email="wrongpass@example.com", password="Password123")
    resp = login(client, "wrongpass@example.com", "IncorrectPassword")
    assert b"Invalid email or password" in resp.data


def test_disabled_account_cannot_login(client, db):
    user = create_verified_user(db, email="disabled@example.com", password="Password123")
    user.is_active_account = False
    db.session.commit()

    resp = login(client, "disabled@example.com", "Password123")
    assert b"disabled" in resp.data.lower()


def test_dashboard_requires_login(client):
    resp = client.get("/dashboard/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_password_reset_flow(client, db, caplog):
    caplog.set_level("INFO")
    create_verified_user(db, email="resetme@example.com", password="OldPassword123")

    client.post("/auth/forgot-password", data={"email": "resetme@example.com"})

    from app.models import PasswordResetToken

    user = User.query.filter_by(email="resetme@example.com").first()
    record = PasswordResetToken.query.filter_by(user_id=user.id).first()
    assert record is not None

    resp = client.post(
        f"/auth/reset-password/{record.token}",
        data={"password": "NewPassword456", "confirm_password": "NewPassword456"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    db.session.refresh(user)
    assert user.check_password("NewPassword456") is True
    assert user.check_password("OldPassword123") is False

    # Old link should now be marked used and rejected on reuse.
    resp2 = client.get(f"/auth/reset-password/{record.token}")
    assert resp2.status_code == 302


def test_forgot_password_does_not_leak_account_existence(client, db):
    resp_known = client.post(
        "/auth/forgot-password", data={"email": "doesnotexist@example.com"}, follow_redirects=True
    )
    assert b"If that account exists" in resp_known.data


def test_change_password_requires_current_password(client, db):
    create_verified_user(db, email="changepw@example.com", password="Password123")
    login(client, "changepw@example.com", "Password123")

    resp = client.post(
        "/auth/change-password",
        data={
            "current_password": "WrongCurrent",
            "new_password": "NewPassword123",
            "confirm_new_password": "NewPassword123",
        },
        follow_redirects=True,
    )
    assert b"incorrect" in resp.data.lower()

    user = User.query.filter_by(email="changepw@example.com").first()
    assert user.check_password("Password123") is True


def test_change_password_success(client, db):
    create_verified_user(db, email="changepw2@example.com", password="Password123")
    login(client, "changepw2@example.com", "Password123")

    resp = client.post(
        "/auth/change-password",
        data={
            "current_password": "Password123",
            "new_password": "BrandNew456",
            "confirm_new_password": "BrandNew456",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    user = User.query.filter_by(email="changepw2@example.com").first()
    assert user.check_password("BrandNew456") is True


def test_account_deletion_removes_user(client, db):
    create_verified_user(db, email="deleteme@example.com", password="Password123")
    login(client, "deleteme@example.com", "Password123")

    resp = client.post(
        "/auth/delete-account",
        data={"password": "Password123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert User.query.filter_by(email="deleteme@example.com").first() is None


def test_account_deletion_requires_correct_password(client, db):
    create_verified_user(db, email="keepme@example.com", password="Password123")
    login(client, "keepme@example.com", "Password123")

    client.post(
        "/auth/delete-account",
        data={"password": "WrongPassword"},
        follow_redirects=True,
    )
    assert User.query.filter_by(email="keepme@example.com").first() is not None
