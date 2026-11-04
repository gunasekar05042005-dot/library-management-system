import threading
from datetime import date

import pytest

from app.auth import create_user
from app.db import connect, get_db
from app.services.borrowing import BorrowError, borrow_book
from tests.conftest import login, register


def add_user(app, email):
    with app.app_context():
        create_user("Member " + email, email, "password123")
        return get_db().execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]


def add_book(app, title="Book", total=1, available=None):
    with app.app_context():
        cur = get_db().execute(
            "INSERT INTO books (title, author, category, total_copies, available_copies) "
            "VALUES (?, 'Author', 'Test', ?, ?)",
            (title, total, total if available is None else available))
        return cur.lastrowid


def copies(app, book_id):
    with app.app_context():
        return get_db().execute(
            "SELECT available_copies FROM books WHERE id = ?", (book_id,)).fetchone()[0]


def loan_count(app, book_id=None):
    with app.app_context():
        sql, args = "SELECT COUNT(*) FROM borrowings", ()
        if book_id:
            sql, args = sql + " WHERE book_id = ?", (book_id,)
        return get_db().execute(sql, args).fetchone()[0]


def test_borrow_reduces_copies_and_sets_14_day_due_date(app):
    uid, bid = add_user(app, "a@test.com"), add_book(app, total=3)
    with app.app_context():
        title, due = borrow_book(get_db(), uid, bid, today=date(2026, 11, 4))
        row = get_db().execute("SELECT * FROM borrowings").fetchone()
    assert due == date(2026, 11, 18)
    assert row["borrowed_at"] == "2026-11-04" and row["due_date"] == "2026-11-18"
    assert row["returned_at"] is None
    assert copies(app, bid) == 2


def test_same_book_cannot_be_borrowed_twice(app):
    uid, bid = add_user(app, "a@test.com"), add_book(app, total=3)
    with app.app_context():
        borrow_book(get_db(), uid, bid)
        with pytest.raises(BorrowError, match="already borrowed"):
            borrow_book(get_db(), uid, bid)
    assert copies(app, bid) == 2 and loan_count(app) == 1


def test_fourth_book_rejected(app):
    uid = add_user(app, "a@test.com")
    ids = [add_book(app, f"Book {i}", total=2) for i in range(4)]
    with app.app_context():
        for bid in ids[:3]:
            borrow_book(get_db(), uid, bid)
        with pytest.raises(BorrowError, match="at most 3"):
            borrow_book(get_db(), uid, ids[3])
    assert copies(app, ids[3]) == 2 and loan_count(app) == 3


def test_book_with_no_copies_rejected(app):
    uid, bid = add_user(app, "a@test.com"), add_book(app, total=1, available=0)
    with app.app_context(), pytest.raises(BorrowError, match="No copies"):
        borrow_book(get_db(), uid, bid)
    assert copies(app, bid) == 0 and loan_count(app) == 0


def test_two_members_cannot_borrow_the_last_copy(app):
    bid = add_book(app, total=1)
    users = [add_user(app, f"u{i}@test.com") for i in range(6)]
    barrier, results = threading.Barrier(len(users)), []

    def attempt(uid):
        db = connect(app.config["DATABASE"])   # each thread has its own connection
        try:
            barrier.wait()                      # release all threads at the same moment
            borrow_book(db, uid, bid)
            results.append("borrowed")
        except BorrowError:
            results.append("blocked")
        finally:
            db.close()

    threads = [threading.Thread(target=attempt, args=(u,)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == ["blocked"] * 5 + ["borrowed"]
    assert copies(app, bid) == 0 and loan_count(app, bid) == 1


def test_borrow_route_and_book_page(client, app):
    bid = add_book(app, "Route Book", total=2)
    register(client)
    login(client)
    assert client.post(f"/borrow/{bid}").status_code == 302
    page = client.get(f"/books/{bid}")
    assert b"Due back by" in page.data and b"Borrow this book" not in page.data
    assert copies(app, bid) == 1


def test_admin_cannot_borrow_and_anonymous_is_redirected(client, app):
    bid = add_book(app)
    assert "/login" in client.post(f"/borrow/{bid}").headers["Location"]
    login(client, "admin@test.com", "adminpass1")
    assert client.post(f"/borrow/{bid}").status_code == 403
    assert copies(app, bid) == 1
