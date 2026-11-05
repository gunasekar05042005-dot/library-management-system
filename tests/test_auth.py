from app.db import get_db
from tests.conftest import login, register


def test_register_creates_member_with_hashed_password(client, app):
    assert register(client).status_code == 302
    with app.app_context():
        user = get_db().execute("SELECT * FROM users WHERE email='member@test.com'").fetchone()
    assert user["role"] == "member"
    assert user["password_hash"] != "password123"


def test_duplicate_email_rejected_case_insensitive(client):
    register(client)
    resp = register(client, email="MEMBER@test.com")
    assert resp.status_code == 200 and b"already exists" in resp.data


def test_short_password_rejected(client):
    resp = register(client, password="short")
    assert b"at least 8 characters" in resp.data


def test_mismatched_passwords_rejected(client):
    assert b"do not match" in register(client, confirm="different123").data


def test_cannot_register_as_admin(client, app):
    register(client, role="admin")          # extra form field must be ignored
    with app.app_context():
        role = get_db().execute("SELECT role FROM users WHERE email='member@test.com'").fetchone()["role"]
    assert role == "member"


def test_login_success_and_wrong_password(client):
    register(client)
    bad = login(client, password="wrongpass1")
    assert bad.status_code == 200 and b"Invalid email or password" in bad.data
    good = login(client)
    assert good.status_code == 302 and good.headers["Location"].endswith("/books")
    with client.session_transaction() as s:
        assert "user_id" in s


def test_anonymous_user_redirected_to_login(client):
    resp = client.get("/books")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_member_blocked_from_admin_but_admin_allowed(client):
    register(client)
    login(client)
    assert client.get("/admin/").status_code == 403
    client.post("/logout")
    login(client, "admin@test.com", "adminpass1")
    assert client.get("/admin/").status_code == 200


def test_logout_requires_post_and_clears_session(client):
    register(client)
    login(client)
    assert client.get("/logout").status_code == 405
    client.post("/logout")
    with client.session_transaction() as s:
        assert "user_id" not in s


def test_login_ignores_external_redirect(client):
    register(client)
    resp = login(client, next="//evil.com")
    assert resp.headers["Location"].endswith("/books")


def test_csrf_blocks_post_without_token(app):
    app.config["CSRF_ENABLED"] = True
    assert register(app.test_client()).status_code == 400
