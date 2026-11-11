"""Admin sign-in page, read-only database viewer, .db file, friendly database errors, several users at once."""
import pytest

import app.auth as auth_module
from app import create_app
from app.db import connect, get_db
from tests.conftest import admin_client, login, register
from tests.test_borrowing import add_book, add_user
from tests.test_edge_cases import member_client
from tests.test_returning import borrow


def admin_sign_in(client, email="admin@test.com", password="adminpass1"):
    return client.post("/admin/login", data={"email": email, "password": password})


# ---------- administrator sign-in ----------
def test_admin_sign_in_page_exists_and_is_linked_everywhere(client):
    page = client.get("/admin/login")
    assert page.status_code == 200 and b"Administrator sign in" in page.data
    assert b"/admin/login" in client.get("/login").data         # from the member login page
    assert b"Admin login" in client.get("/register").data       # from the navigation bar


def test_admin_can_sign_in_and_lands_on_the_dashboard(client):
    resp = admin_sign_in(client)
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/admin/")
    assert client.get("/admin/").status_code == 200


def test_admin_can_still_use_the_ordinary_login(client):
    resp = login(client, "admin@test.com", "adminpass1")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/admin/")


@pytest.mark.parametrize("email,password", [
    ("member@test.com", "password123"),       # a real member, right password: still refused here
    ("admin@test.com", "wrong-password"),
    ("nobody@test.com", "password123"),
    ("", ""),
])
def test_admin_page_refuses_everyone_but_admins_with_one_generic_message(client, email, password):
    register(client)
    resp = admin_sign_in(client, email, password)
    assert resp.status_code == 200 and b"Invalid administrator email or password" in resp.data
    with client.session_transaction() as s:
        assert "user_id" not in s


def test_admin_sign_in_also_checks_a_hash_for_unknown_emails(client, monkeypatch):
    calls = []
    real = auth_module.check_password_hash
    monkeypatch.setattr(auth_module, "check_password_hash", lambda *a: calls.append(1) or real(*a))
    admin_sign_in(client, "nobody@test.com", "whatever123")
    assert len(calls) == 1


def test_signed_in_users_are_sent_home_from_the_admin_sign_in_page(app):
    assert member_client(app, "m@test.com").get("/admin/login").headers["Location"].endswith("/books")
    assert admin_client(app).get("/admin/login").headers["Location"].endswith("/admin/")


# ---------- read-only database viewer ----------
def test_admin_sees_every_table_but_never_password_hashes(app):
    uid = add_user(app, "a@test.com")
    bid = add_book(app, "Visible Book", total=2)
    borrow(app, uid, bid)
    admin = admin_client(app)

    overview = admin.get("/admin/database")
    assert overview.status_code == 200 and b"test.db" in overview.data and b"read-only" in overview.data

    users = admin.get("/admin/database/users").data
    assert b"admin@test.com" in users and b"a@test.com" in users          # admins and members
    assert b"password_hash" not in users and b"scrypt:" not in users and b"pbkdf2:" not in users
    assert b"Visible Book" in admin.get("/admin/database/books").data
    loans = admin.get("/admin/database/borrowings").data
    assert b"due_date" in loans and b"returned_at" in loans


def test_database_viewer_only_opens_the_three_known_tables(app):
    admin = admin_client(app)
    for name in ("sqlite_master", "users;DROP TABLE users", "nothing"):
        assert admin.get(f"/admin/database/{name}").status_code == 404
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_database_viewer_is_for_admins_only(app, client):
    for path in ("/admin/database", "/admin/database/users"):
        assert "/login" in client.get(path).headers["Location"]
        assert member_client(app, f"m{len(path)}@test.com").get(path).status_code == 403


def test_database_viewer_pages_through_rows(app):
    for i in range(20):
        add_user(app, f"u{i}@test.com")
    page = admin_client(app).get("/admin/database/users")
    assert b"Page 1 of 2" in page.data and b"21 rows in users" in page.data


# ---------- database file and errors ----------
def test_default_database_file_ends_in_dot_db():
    assert create_app({"TESTING": True}).config["DATABASE"].endswith("library.db")


def test_a_brand_new_database_file_gets_its_tables_automatically(tmp_path):
    fresh = create_app({"TESTING": True, "DATABASE": str(tmp_path / "brand_new.db")})
    with fresh.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0


def test_a_locked_database_gives_a_friendly_page_not_a_crash(app):
    app.config["DB_TIMEOUT"] = 0.2
    c = member_client(app, "m@test.com")
    blocker = connect(app.config["DATABASE"])
    blocker.execute("BEGIN IMMEDIATE")                 # another program is writing to the file
    try:
        resp = c.post("/profile", data={"full_name": "New Name", "phone": ""})
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()
    assert resp.status_code == 503 and b"database is busy" in resp.data


# ---------- several users at once ----------
def test_different_browsers_can_be_signed_in_as_different_users_at_once(app):
    first, second, admin = (member_client(app, "a@test.com"), member_client(app, "b@test.com"),
                            admin_client(app))
    assert b"a@test.com" in first.get("/profile").data and b"b@test.com" not in first.get("/profile").data
    assert b"b@test.com" in second.get("/profile").data and b"a@test.com" not in second.get("/profile").data
    assert admin.get("/admin/").status_code == 200 and first.get("/admin/").status_code == 403


def test_one_browser_holds_one_session_so_a_second_login_page_redirects(app):
    c = member_client(app, "a@test.com")             # all tabs of one browser share this cookie
    assert c.get("/login").headers["Location"].endswith("/books")


def test_stale_form_after_signing_in_elsewhere_explains_what_happened(app):
    app.config["CSRF_ENABLED"] = True
    resp = app.test_client().post("/register", data={"full_name": "X"})
    assert resp.status_code == 400 and b"signed in or out in another tab" in resp.data
