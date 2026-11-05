"""Negative, edge-case, refresh and multi-tab tests (a 'tab' = a request made from an old page)."""
import re
import sqlite3
import threading
import time

import pytest

from app.db import connect, get_db
from app.services.borrowing import BorrowError, borrow_book
from tests.conftest import login, register
from tests.test_borrowing import add_book, add_user, copies, loan_count


def member_client(app, email):
    """A separate 'browser': its own cookie jar, already logged in."""
    c = app.test_client()
    register(c, email=email)
    login(c, email=email)
    return c


def only_loan_id(app):
    with app.app_context():
        return get_db().execute("SELECT id FROM borrowings").fetchone()["id"]


class SlowDB:
    """Pauses after the 'how many loans?' query. This widens the gap between checking and
    writing, so a missing lock cannot get away with it just because the code runs fast."""

    def __init__(self, db):
        self._db = db

    def execute(self, sql, *args):
        cursor = self._db.execute(sql, *args)
        if sql.lstrip().startswith("SELECT COUNT(*)"):
            time.sleep(0.05)
        return cursor

    def __getattr__(self, name):
        return getattr(self._db, name)


def race(app, jobs):
    """Run borrow_book for every (user_id, book_id) at the same instant, one connection each."""
    barrier, results = threading.Barrier(len(jobs)), []

    def attempt(uid, bid):
        db = SlowDB(connect(app.config["DATABASE"]))
        try:
            barrier.wait()
            borrow_book(db, uid, bid)
            results.append("borrowed")
        except BorrowError:
            results.append("blocked")
        finally:
            db.close()

    threads = [threading.Thread(target=attempt, args=job) for job in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == len(jobs)         # nothing crashed with an unexpected error
    return results


# ---------- authentication: negative and boundary ----------
@pytest.mark.parametrize("email,password", [
    ("nobody@test.com", "password123"),      # unknown email
    ("member@test.com", "wrongpassword"),    # wrong password
    ("member@test.com", ""),                 # empty password
    ("", ""),                                # empty form
    ("' OR '1'='1", "' OR '1'='1"),          # SQL injection attempt
])
def test_invalid_logins_get_one_generic_error(client, email, password):
    register(client)
    resp = login(client, email, password)
    assert resp.status_code == 200 and b"Invalid email or password" in resp.data
    with client.session_transaction() as s:
        assert "user_id" not in s


def test_login_email_is_case_insensitive(client):
    register(client)
    assert login(client, email="MEMBER@Test.com").status_code == 302


@pytest.mark.parametrize("kwargs,message", [
    ({"name": "   "}, b"Full name is required"),
    ({"email": "not-an-email"}, b"valid email"),
    ({"email": "a@b"}, b"valid email"),
    ({"password": "1234567"}, b"at least 8"),          # one short of the minimum
    ({"password": "x" * 129}, b"at most 128"),         # one over the maximum
])
def test_invalid_registration_is_rejected(client, app, kwargs, message):
    resp = register(client, **kwargs)
    assert resp.status_code == 200 and message in resp.data
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1   # only the admin


def test_password_of_exactly_minimum_length_is_accepted(client):
    assert register(client, password="12345678").status_code == 302


# ---------- borrowing through the web UI ----------
def test_unavailable_book_cannot_be_borrowed_even_with_a_forged_request(app):
    bid = add_book(app, total=1, available=0)
    c = member_client(app, "m@test.com")
    page = c.get(f"/books/{bid}")
    assert b"No copies are available" in page.data and b"Borrow this book" not in page.data
    resp = c.post(f"/borrow/{bid}", follow_redirects=True)
    assert b"No copies of this book are available" in resp.data
    assert loan_count(app) == 0 and copies(app, bid) == 0


def test_fourth_book_is_blocked_in_ui_and_by_forged_request(app):
    ids = [add_book(app, f"Book {i}", total=2) for i in range(4)]
    c = member_client(app, "m@test.com")
    for bid in ids[:3]:
        c.post(f"/borrow/{bid}")
    page = c.get(f"/books/{ids[3]}")
    assert b"the maximum" in page.data and b"Borrow this book" not in page.data
    resp = c.post(f"/borrow/{ids[3]}", follow_redirects=True)
    assert b"at most 3" in resp.data
    assert loan_count(app) == 3 and copies(app, ids[3]) == 2


def test_borrowing_a_book_that_does_not_exist(app):
    c = member_client(app, "m@test.com")
    resp = c.post("/borrow/9999", follow_redirects=True)
    assert resp.status_code == 404 and b"does not exist" in resp.data


def test_member_cannot_return_another_members_loan(app):
    bid = add_book(app, total=2)
    owner, intruder = member_client(app, "a@test.com"), member_client(app, "b@test.com")
    owner.post(f"/borrow/{bid}")
    resp = intruder.post(f"/return/{only_loan_id(app)}", follow_redirects=True)
    assert b"not found" in resp.data
    assert copies(app, bid) == 1             # the owner still has the book


# ---------- browser refresh ----------
def test_refreshing_after_borrowing_does_not_borrow_again(app):
    bid = add_book(app, total=3)
    c = member_client(app, "m@test.com")
    first = c.post(f"/borrow/{bid}")
    assert first.status_code == 302 and first.headers["Location"].endswith(f"/books/{bid}")
    for _ in range(3):                       # a refresh after the redirect is a plain GET
        assert c.get(f"/books/{bid}").status_code == 200
    assert copies(app, bid) == 2 and loan_count(app, bid) == 1
    again = c.post(f"/borrow/{bid}", follow_redirects=True)   # "Confirm form resubmission"
    assert b"already borrowed" in again.data
    assert copies(app, bid) == 2 and loan_count(app, bid) == 1


def test_refreshing_the_dashboard_changes_nothing(app):
    bid = add_book(app, total=2)
    c = member_client(app, "m@test.com")
    c.post(f"/borrow/{bid}")
    for _ in range(3):
        assert b"1 of 3" in c.get("/dashboard").data
    assert copies(app, bid) == 1 and loan_count(app) == 1


# ---------- multiple tabs / browsers ----------
def test_stale_return_tab_cannot_return_twice(app):
    bid = add_book(app, total=2)
    c = member_client(app, "m@test.com")
    c.post(f"/borrow/{bid}")
    loan_id = only_loan_id(app)
    tab_a = c.post(f"/return/{loan_id}", follow_redirects=True)
    tab_b = c.post(f"/return/{loan_id}", follow_redirects=True)   # old tab still showed "Return"
    assert b"You returned" in tab_a.data and b"already been returned" in tab_b.data
    assert copies(app, bid) == 2             # restored once, not twice


def test_stale_borrow_page_after_another_member_takes_the_last_copy(app):
    bid = add_book(app, total=1)
    tab_1, tab_2 = member_client(app, "one@test.com"), member_client(app, "two@test.com")
    assert b"Borrow this book" in tab_2.get(f"/books/{bid}").data   # copy looked free
    tab_1.post(f"/borrow/{bid}")                                    # someone else takes it
    resp = tab_2.post(f"/borrow/{bid}", follow_redirects=True)      # stale button clicked
    assert b"No copies of this book are available" in resp.data
    assert copies(app, bid) == 0 and loan_count(app, bid) == 1


def test_stale_tab_is_rejected_after_logout_in_another_tab(app):
    app.config["CSRF_ENABLED"] = True
    token_re = re.compile(rb'name="csrf_token" value="([^"]+)"')

    def token(client, path):
        return token_re.search(client.get(path).data).group(1).decode()

    bid = add_book(app, total=2)
    c = app.test_client()
    c.post("/register", data={"full_name": "T", "email": "t@test.com", "password": "password123",
                              "confirm_password": "password123", "csrf_token": token(c, "/register")})
    c.post("/login", data={"email": "t@test.com", "password": "password123",
                           "csrf_token": token(c, "/login")})
    stale = token(c, f"/books/{bid}")                       # tab B loads the book page
    c.post("/logout", data={"csrf_token": stale})           # tab A logs out
    resp = c.post(f"/borrow/{bid}", data={"csrf_token": stale})   # tab B clicks Borrow
    assert resp.status_code == 400
    assert loan_count(app) == 0 and copies(app, bid) == 2


# ---------- simultaneous requests ----------
def test_double_click_by_one_member_borrows_once(app):
    uid, bid = add_user(app, "a@test.com"), add_book(app, total=5)
    results = race(app, [(uid, bid)] * 5)
    assert sorted(results) == ["blocked"] * 4 + ["borrowed"]
    assert copies(app, bid) == 4 and loan_count(app, bid) == 1


def test_three_book_limit_holds_under_simultaneous_requests(app):
    uid = add_user(app, "a@test.com")
    ids = [add_book(app, f"Book {i}", total=2) for i in range(6)]
    results = race(app, [(uid, b) for b in ids])
    assert results.count("borrowed") == 3 and results.count("blocked") == 3
    assert loan_count(app) == 3


# ---------- the database as the last line of defence ----------
@pytest.mark.parametrize("sql", [
    "INSERT INTO books (title, author, category, total_copies, available_copies) VALUES ('X','Y','Z',1,-1)",
    "INSERT INTO books (title, author, category, total_copies, available_copies) VALUES ('X','Y','Z',1,2)",
    "INSERT INTO users (full_name, email, password_hash, role) VALUES ('A','x@test.com','h','superuser')",
    "INSERT INTO users (full_name, email, password_hash) VALUES ('A','ADMIN@TEST.COM','h')",
    "INSERT INTO borrowings (user_id, book_id, borrowed_at, due_date) VALUES (999,999,'2026-01-01','2026-01-15')",
], ids=["negative copies", "available above total", "invalid role", "duplicate email", "unknown user and book"])
def test_database_rejects_invalid_rows(app, sql):
    with app.app_context(), pytest.raises(sqlite3.IntegrityError):
        get_db().execute(sql)


def test_database_rejects_a_second_active_loan_of_the_same_book(app):
    uid, bid = add_user(app, "a@test.com"), add_book(app, total=2)
    insert = ("INSERT INTO borrowings (user_id, book_id, borrowed_at, due_date) "
              "VALUES (?, ?, '2026-11-04', '2026-11-18')")
    with app.app_context():
        get_db().execute(insert, (uid, bid))
        with pytest.raises(sqlite3.IntegrityError):
            get_db().execute(insert, (uid, bid))
