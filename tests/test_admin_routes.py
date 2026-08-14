from app.models import User
from app.services.ai import get_provider_manager
from tests.conftest import create_verified_user, login


def _make_admin(db, email="admin@example.com", password="Password123"):
    user = create_verified_user(db, email=email, password=password)
    user.is_admin = True
    db.session.commit()
    return user


def test_non_admin_gets_403_on_dashboard(client, db):
    create_verified_user(db, email="regular@example.com", password="Password123")
    login(client, "regular@example.com", "Password123")

    resp = client.get("/admin/")
    assert resp.status_code == 403


def test_anonymous_redirected_to_login(client, db):
    resp = client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_non_admin_gets_403_on_every_admin_route(client, db):
    create_verified_user(db, email="regular2@example.com", password="Password123")
    login(client, "regular2@example.com", "Password123")

    assert client.get("/admin/users").status_code == 403
    assert client.get("/admin/logs").status_code == 403
    assert client.get("/admin/ai-providers").status_code == 403
    assert client.post("/admin/ai-providers/limits", data={"daily_limit": 5, "monthly_limit": 100}).status_code == 403


def test_admin_can_access_dashboard(client, db):
    _make_admin(db)
    login(client, "admin@example.com", "Password123")

    resp = client.get("/admin/")
    assert resp.status_code == 200
    assert b"Total users" in resp.data


def test_dashboard_reflects_real_user_count(client, db):
    _make_admin(db)
    create_verified_user(db, email="extra1@example.com", password="Password123")
    create_verified_user(db, email="extra2@example.com", password="Password123")
    login(client, "admin@example.com", "Password123")

    resp = client.get("/admin/")
    assert resp.status_code == 200
    assert User.query.count() == 3


def test_admin_can_disable_and_enable_user(client, db):
    _make_admin(db)
    target = create_verified_user(db, email="target@example.com", password="Password123")
    login(client, "admin@example.com", "Password123")

    resp = client.post(f"/admin/users/{target.id}/toggle-active", follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(target)
    assert target.is_active_account is False

    client.post(f"/admin/users/{target.id}/toggle-active", follow_redirects=True)
    db.session.refresh(target)
    assert target.is_active_account is True


def test_disabled_user_cannot_login(client, db):
    _make_admin(db)
    target = create_verified_user(db, email="disabledlogin@example.com", password="Password123")
    login(client, "admin@example.com", "Password123")
    client.post(f"/admin/users/{target.id}/toggle-active")
    client.get("/auth/logout")

    resp = login(client, "disabledlogin@example.com", "Password123")
    assert b"disabled" in resp.data.lower()


def test_admin_cannot_disable_own_account(client, db):
    admin = _make_admin(db)
    login(client, "admin@example.com", "Password123")

    resp = client.post(f"/admin/users/{admin.id}/toggle-active", follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(admin)
    assert admin.is_active_account is True


def test_admin_can_delete_user(client, db):
    _make_admin(db)
    target = create_verified_user(db, email="deleteme@example.com", password="Password123")
    target_id = target.id
    login(client, "admin@example.com", "Password123")

    resp = client.post(f"/admin/users/{target_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert db.session.get(User, target_id) is None


def test_admin_cannot_delete_own_account_via_admin_route(client, db):
    admin = _make_admin(db)
    login(client, "admin@example.com", "Password123")

    resp = client.post(f"/admin/users/{admin.id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert db.session.get(User, admin.id) is not None


def test_user_list_search_filters_by_email(client, db):
    _make_admin(db)
    create_verified_user(db, email="findme@example.com", password="Password123")
    create_verified_user(db, email="different@example.com", password="Password123")
    login(client, "admin@example.com", "Password123")

    resp = client.get("/admin/users?q=findme")
    assert b"findme@example.com" in resp.data
    assert b"different@example.com" not in resp.data


def test_logs_page_shows_activity_from_any_user(client, db):
    _make_admin(db)
    create_verified_user(db, email="loguser@example.com", password="Password123")
    login(client, "loguser@example.com", "Password123")
    client.get("/auth/logout")

    login(client, "admin@example.com", "Password123")
    resp = client.get("/admin/logs")
    assert resp.status_code == 200
    assert b"loguser@example.com" in resp.data


def test_ai_providers_page_never_exposes_raw_keys(client, db, app):
    _make_admin(db)
    login(client, "admin@example.com", "Password123")

    from app.services.ai.provider_manager import AIProviderManager
    fake_manager = AIProviderManager({
        "AI_PROVIDER_ORDER": ["gemini"],
        "GEMINI_API_KEYS": ["AIzaSySUPER-SECRET-KEY-VALUE-12345"],
        "GEMINI_MODEL": "gemini-1.5-flash",
    })
    app.extensions["ai_provider_manager"] = fake_manager

    resp = client.get("/admin/ai-providers")
    assert resp.status_code == 200
    assert b"AIzaSySUPER-SECRET-KEY-VALUE-12345" not in resp.data
    assert b"SUPER-SECRET" not in resp.data


def test_admin_can_update_usage_limits(client, db, app):
    _make_admin(db)
    login(client, "admin@example.com", "Password123")

    resp = client.post(
        "/admin/ai-providers/limits", data={"daily_limit": 42, "monthly_limit": 999}, follow_redirects=True
    )
    assert resp.status_code == 200

    from app.services.system_settings import get_setting
    assert get_setting("AI_DAILY_REQUEST_LIMIT_PER_USER") == "42"
    assert get_setting("AI_MONTHLY_REQUEST_LIMIT_PER_USER") == "999"

    manager = get_provider_manager(app)
    assert manager.config["AI_DAILY_REQUEST_LIMIT_PER_USER"] == 42
    assert manager.config["AI_MONTHLY_REQUEST_LIMIT_PER_USER"] == 999


def test_update_limits_rejects_invalid_values(client, db):
    _make_admin(db)
    login(client, "admin@example.com", "Password123")

    resp = client.post(
        "/admin/ai-providers/limits", data={"daily_limit": -5, "monthly_limit": 100}, follow_redirects=True
    )
    assert resp.status_code == 200
    from app.services.system_settings import get_setting
    assert get_setting("AI_DAILY_REQUEST_LIMIT_PER_USER") is None


def test_admin_can_update_provider_order(client, db, app):
    _make_admin(db)
    login(client, "admin@example.com", "Password123")

    resp = client.post("/admin/ai-providers/order", data={"provider_order": "groq, gemini"}, follow_redirects=True)
    assert resp.status_code == 200

    from app.services.system_settings import get_setting
    assert get_setting("AI_PROVIDER_ORDER") == "groq,gemini"

    manager = get_provider_manager(app)
    assert manager.provider_order == ["groq", "gemini"]


def test_update_provider_order_rejects_unknown_provider(client, db):
    _make_admin(db)
    login(client, "admin@example.com", "Password123")

    resp = client.post("/admin/ai-providers/order", data={"provider_order": "fakeprovider"}, follow_redirects=True)
    assert resp.status_code == 200
    from app.services.system_settings import get_setting
    assert get_setting("AI_PROVIDER_ORDER") is None
