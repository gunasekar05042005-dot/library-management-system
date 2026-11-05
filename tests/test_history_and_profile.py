"""Borrowing history (BR-05) and the profile page."""
from datetime import date

import pytest

from app.db import get_db
from app.services.borrowing import return_book
from tests.conftest import admin_client, uid_of
from tests.test_borrowing import add_book
from tests.test_edge_cases import member_client
from tests.test_returning import borrow


def test_history_shows_all_three_statuses_and_only_own_records(app):
    mine, other = member_client(app, "me@test.com"), member_client(app, "other@test.com")
    me, them = uid_of(app, "me@test.com"), uid_of(app, "other@test.com")
    late, done, fresh, secret = (add_book(app, t, total=3) for t in
                                 ("Late Book", "Done Book", "Fresh Book", "Secret Book"))
    borrow(app, me, late, today=date(2020, 1, 1))
    loan = borrow(app, me, done, today=date(2020, 2, 1))
    with app.app_context():
        return_book(get_db(), me, loan, today=date(2020, 2, 5))
    borrow(app, me, fresh)
    borrow(app, them, secret)

    page = mine.get("/history")
    for title in (b"Late Book", b"Done Book", b"Fresh Book"):
        assert title in page.data
    assert b"Secret Book" not in page.data
    assert b">Overdue</span>" in page.data and b">Returned</span>" in page.data and b">Borrowed</span>" in page.data

    only = lambda status: mine.get("/history", query_string={"status": status}).data
    assert b"Done Book" in only("returned") and b"Late Book" not in only("returned")
    assert b"Late Book" in only("overdue") and b"Fresh Book" not in only("overdue")
    assert b"Fresh Book" in only("borrowed") and b"Done Book" not in only("borrowed")


def test_history_cannot_be_pointed_at_another_member(app):
    mine = member_client(app, "me@test.com")
    member_client(app, "other@test.com")
    borrow(app, uid_of(app, "other@test.com"), add_book(app, "Secret Book", total=2))
    resp = mine.get("/history", query_string={"user_id": uid_of(app, "other@test.com")})
    assert b"Secret Book" not in resp.data       # the member id always comes from the session


def test_history_requires_a_member(client, app):
    assert "/login" in client.get("/history").headers["Location"]
    assert admin_client(app).get("/history").status_code == 403


def test_history_is_paginated(app):
    c, uid = member_client(app, "m@test.com"), uid_of(app, "m@test.com")
    with app.app_context():
        from app.services.borrowing import borrow_book
        db = get_db()
        for i in range(20):
            bid = db.execute("INSERT INTO books (title, author, category, total_copies, available_copies) "
                             "VALUES (?, 'A', 'C', 1, 1)", (f"B{i}",)).lastrowid
            borrow_book(db, uid, bid)
            loan = db.execute("SELECT id FROM borrowings WHERE book_id = ?", (bid,)).fetchone()["id"]
            return_book(db, uid, loan)
    page1, page2 = c.get("/history"), c.get("/history", query_string={"page": 2})
    assert page1.data.count(b"<tr>") == 16 and b"Page 1 of 2" in page1.data     # header + 15 rows
    assert page2.data.count(b"<tr>") == 6


# ---------- profile ----------
def test_profile_view_and_update(app):
    c = member_client(app, "p@test.com")
    assert b"p@test.com" in c.get("/profile").data
    resp = c.post("/profile", data={"full_name": "New Name", "phone": "+91 98765 43210"}, follow_redirects=True)
    assert b"Profile updated" in resp.data and b"New Name" in resp.data
    with app.app_context():
        row = get_db().execute("SELECT full_name, phone FROM users WHERE email='p@test.com'").fetchone()
    assert (row["full_name"], row["phone"]) == ("New Name", "+91 98765 43210")


@pytest.mark.parametrize("data,message", [
    ({"full_name": "", "phone": ""}, b"Full name is required"),
    ({"full_name": "   ", "phone": ""}, b"Full name is required"),
    ({"full_name": "N" * 101, "phone": ""}, b"at most 100"),
    ({"full_name": "Ok", "phone": "abc"}, b"valid phone"),
    ({"full_name": "Ok", "phone": "123"}, b"valid phone"),
])
def test_profile_validation_rejects_bad_input_and_changes_nothing(app, data, message):
    c = member_client(app, "p@test.com")
    resp = c.post("/profile", data=data)
    assert resp.status_code == 200 and message in resp.data
    with app.app_context():
        assert get_db().execute("SELECT full_name FROM users WHERE email='p@test.com'").fetchone()[0] == "Test Member"


def test_profile_cannot_change_email_or_role(app):
    c = member_client(app, "p@test.com")
    c.post("/profile", data={"full_name": "Same", "phone": "", "email": "hacker@test.com", "role": "admin"})
    with app.app_context():
        row = get_db().execute("SELECT email, role, full_name FROM users WHERE id = ?", (uid_of(app, "p@test.com"),)).fetchone()
    assert (row["email"], row["role"], row["full_name"]) == ("p@test.com", "member", "Same")


def test_blank_phone_clears_the_phone_number(app):
    c = member_client(app, "p@test.com")
    c.post("/profile", data={"full_name": "A", "phone": "98765 43210"})
    c.post("/profile", data={"full_name": "A", "phone": ""})
    with app.app_context():
        assert get_db().execute("SELECT phone FROM users WHERE email='p@test.com'").fetchone()[0] is None


def test_profile_requires_login_and_works_for_admin(client, app):
    assert "/login" in client.get("/profile").headers["Location"]
    admin = admin_client(app)
    assert admin.post("/profile", data={"full_name": "Chief Admin", "phone": ""}).status_code == 302
    assert b"Chief Admin" in admin.get("/profile").data
