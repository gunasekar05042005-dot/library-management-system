import threading
from datetime import date

import pytest

from app.db import connect, get_db
from app.services.borrowing import ReturnError, borrow_book, return_book
from tests.conftest import login, register
from tests.test_borrowing import add_book, add_user, copies


def borrow(app, uid, bid, today=None):
    with app.app_context():
        borrow_book(get_db(), uid, bid, today=today)
        return get_db().execute(
            "SELECT id FROM borrowings WHERE user_id = ? AND book_id = ? ORDER BY id DESC",
            (uid, bid)).fetchone()["id"]


def test_return_marks_loan_returned_and_restores_copy(app):
    uid, bid = add_user(app, "a@test.com"), add_book(app, total=2)
    loan_id = borrow(app, uid, bid, today=date(2026, 11, 1))   # fixed dates: the result must not depend on the day the test runs
    assert copies(app, bid) == 1
    with app.app_context():
        title = return_book(get_db(), uid, loan_id, today=date(2026, 11, 10))
        row = get_db().execute("SELECT * FROM borrowings WHERE id = ?", (loan_id,)).fetchone()
    assert title == "Book" and row["returned_at"] == "2026-11-10"   # record kept for history
    assert copies(app, bid) == 2


def test_book_cannot_be_returned_twice(app):
    uid, bid = add_user(app, "a@test.com"), add_book(app, total=2)
    loan_id = borrow(app, uid, bid)
    with app.app_context():
        return_book(get_db(), uid, loan_id)
        with pytest.raises(ReturnError, match="already been returned"):
            return_book(get_db(), uid, loan_id)
    assert copies(app, bid) == 2            # not 3: the copy count was increased only once


def test_member_cannot_return_someone_elses_loan(app):
    owner, other = add_user(app, "a@test.com"), add_user(app, "b@test.com")
    bid = add_book(app, total=2)
    loan_id = borrow(app, owner, bid)
    with app.app_context(), pytest.raises(ReturnError, match="not found"):
        return_book(get_db(), other, loan_id)
    assert copies(app, bid) == 1            # loan still open


def test_unknown_borrowing_id_rejected(app):
    uid = add_user(app, "a@test.com")
    with app.app_context(), pytest.raises(ReturnError, match="not found"):
        return_book(get_db(), uid, 9999)


def test_same_book_can_be_borrowed_again_after_return(app):
    uid, bid = add_user(app, "a@test.com"), add_book(app, total=1)
    loan_id = borrow(app, uid, bid)
    with app.app_context():
        return_book(get_db(), uid, loan_id)
    borrow(app, uid, bid)                   # allowed: the unique index only covers ACTIVE loans
    assert copies(app, bid) == 0


def test_double_submit_returns_the_copy_only_once(app):
    uid, bid = add_user(app, "a@test.com"), add_book(app, total=3)
    loan_id = borrow(app, uid, bid)
    barrier, results = threading.Barrier(5), []

    def attempt():
        db = connect(app.config["DATABASE"])
        try:
            barrier.wait()
            return_book(db, uid, loan_id)
            results.append("returned")
        except ReturnError:
            results.append("refused")
        finally:
            db.close()

    threads = [threading.Thread(target=attempt) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["refused"] * 4 + ["returned"]
    assert copies(app, bid) == 3            # back to total, never above it


def test_dashboard_page_return_flow_and_overdue_flag(client, app):
    bid = add_book(app, "Late Book", total=2)
    register(client)
    login(client)
    with app.app_context():
        uid = get_db().execute("SELECT id FROM users WHERE email='member@test.com'").fetchone()["id"]
    loan_id = borrow(app, uid, bid, today=date(2020, 1, 1))
    page = client.get("/dashboard")
    assert b"Late Book" in page.data and b"Overdue" in page.data
    assert client.post(f"/return/{loan_id}").status_code == 302
    assert b"no borrowed books" in client.get("/dashboard").data
    assert b"already been returned" in client.post(f"/return/{loan_id}", follow_redirects=True).data
    assert copies(app, bid) == 2


def test_return_route_is_post_only_and_members_only(client, app):
    assert client.get("/return/1").status_code == 405
    assert "/login" in client.post("/return/1").headers["Location"]
    login(client, "admin@test.com", "adminpass1")
    assert client.post("/return/1").status_code == 403
