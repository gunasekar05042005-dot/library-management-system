"""Regression tests: one for every problem found in the code review."""
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from flask import Flask
from flask.sessions import SecureCookieSessionInterface

import app.auth as auth_module
from app import create_app
from app.db import get_db, init_db
from app.services.borrowing import borrow_book, return_book
from app.services.clock import today as local_today
from tests.conftest import login, register, uid_of
from tests.test_borrowing import add_book, add_user, copies
from tests.test_edge_cases import member_client


def forged_cookie(secret, **session):
    forger = Flask("attacker")
    forger.secret_key = secret
    return SecureCookieSessionInterface().get_signing_serializer(forger).dumps(session)


# 1. Forgeable sessions (hard-coded SECRET_KEY)
def test_cookie_signed_with_the_old_public_default_key_is_useless(app, client):
    client.set_cookie("session", forged_cookie("dev-only-change-me", user_id=uid_of(app, "admin@test.com")))
    resp = client.get("/admin/")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_secret_key_is_random_and_stable_between_runs(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    first, second = create_app({"TESTING": True}), create_app({"TESTING": True})
    key = first.config["SECRET_KEY"]
    assert key == second.config["SECRET_KEY"] and key != "dev-only-change-me" and len(key) >= 64


def test_even_a_cookie_signed_with_the_real_key_needs_the_password_fingerprint(app, client):
    real = app.session_interface.get_signing_serializer(app).dumps({"user_id": uid_of(app, "admin@test.com")})
    client.set_cookie("session", real)
    assert client.get("/admin/").status_code == 302


# 2. Login timing leak
@pytest.mark.parametrize("email", ["nobody@test.com", "m@test.com"])
def test_a_password_hash_is_checked_whether_or_not_the_email_exists(app, client, monkeypatch, email):
    member_client(app, "m@test.com")
    calls = []
    real = auth_module.check_password_hash
    monkeypatch.setattr(auth_module, "check_password_hash", lambda *a: calls.append(1) or real(*a))
    app.test_client().post("/login", data={"email": email, "password": "wrong-password"})
    assert len(calls) == 1


# 3. Input limits
def test_overlong_name_and_email_are_rejected(client):
    assert b"at most 100" in register(client, name="N" * 101).data
    assert b"valid email" in register(client, email="a" * 250 + "@x.com").data


def test_oversized_request_body_is_refused(client):
    resp = client.post("/register", data={"full_name": "N" * 70_000, "email": "a@b.co", "password": "password123"})
    assert resp.status_code == 413 and b"Request too large" in resp.data


# 4. Misleading IntegrityError message
def test_a_genuine_database_fault_is_not_reported_as_already_borrowed(app):
    bid = add_book(app, total=2)
    with app.app_context():
        with pytest.raises(sqlite3.IntegrityError):          # unknown user: a foreign-key failure
            borrow_book(get_db(), 99999, bid)
        assert not get_db().in_transaction                   # and the transaction was rolled back
    assert copies(app, bid) == 2


# 5. Loan that can never be returned
def test_return_never_writes_a_date_before_the_borrow_date(app):
    uid, bid = add_user(app, "a@test.com"), add_book(app, total=2)
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO borrowings (user_id, book_id, borrowed_at, due_date) VALUES (?, ?, '2099-01-01', '2099-01-15')", (uid, bid))
        db.execute("UPDATE books SET available_copies = 1 WHERE id = ?", (bid,))
        loan = db.execute("SELECT id FROM borrowings").fetchone()["id"]
        from datetime import date
        return_book(db, uid, loan, today=date(2026, 11, 4))   # a clock that is "behind" the borrow date
        assert db.execute("SELECT returned_at FROM borrowings WHERE id = ?", (loan,)).fetchone()[0] == "2099-01-01"
    assert copies(app, bid) == 2


# 6. Security headers and cookie flags
def test_security_headers_are_sent(client):
    headers = client.get("/login").headers
    assert headers["X-Frame-Options"] == "DENY" and headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Referrer-Policy"] == "same-origin"


def test_session_cookie_flags(app, tmp_path):
    register(app.test_client())
    cookie = login(app.test_client()).headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Secure" not in cookie
    secure = create_app({"TESTING": True, "DATABASE": app.config["DATABASE"], "CSRF_ENABLED": False,
                         "SESSION_COOKIE_SECURE": True})
    assert "Secure" in login(secure.test_client()).headers["Set-Cookie"]


# 8. 'next' after a POST
def test_only_page_views_are_resumed_after_login(client):
    post = client.post("/borrow/1")
    assert post.headers["Location"].endswith("/login")        # no ?next=/borrow/1 (it would 405)
    assert "next=" in client.get("/books").headers["Location"]


# 9. Static files cost a user lookup
def test_static_files_do_not_query_the_user_table(app, monkeypatch):
    c = member_client(app, "m@test.com")
    calls = []
    real = auth_module.get_db
    monkeypatch.setattr(auth_module, "get_db", lambda: calls.append(1) or real())
    assert c.get("/static/css/style.css").status_code == 200
    assert calls == []


# Schema upgrades, timezone, defaults
@pytest.mark.skipif(sqlite3.sqlite_version_info < (3, 35), reason="needs DROP COLUMN")
def test_old_databases_are_upgraded(app):
    with app.app_context():
        get_db().execute("ALTER TABLE books DROP COLUMN description")
        init_db()
        assert "description" in {r["name"] for r in get_db().execute("PRAGMA table_info(books)")}


def test_today_uses_the_configured_timezone(app):
    app.config["TIMEZONE"] = "Pacific/Kiritimati"
    with app.app_context():
        assert local_today() == datetime.now(ZoneInfo("Pacific/Kiritimati")).date()


def test_reset_link_is_hidden_unless_demo_mode_is_on(monkeypatch):
    monkeypatch.delenv("SHOW_RESET_LINK", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert create_app({"TESTING": True}).config["SHOW_RESET_LINK"] is False
