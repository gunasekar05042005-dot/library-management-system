from datetime import date

from app.db import get_db
from app.services.borrowing import return_book
from app.services.stats import admin_stats
from tests.conftest import login, register
from tests.test_borrowing import add_book, add_user
from tests.test_returning import borrow

TODAY = date(2026, 11, 4)


def test_admin_stats_are_calculated_from_real_data(app):
    u1, u2 = add_user(app, "a@test.com"), add_user(app, "b@test.com")
    a = add_book(app, "Book A", total=5)                 # well stocked
    b = add_book(app, "Book B", total=2)                 # low once borrowed
    add_book(app, "Book C", total=1)                     # low
    add_book(app, "Book D", total=0, available=0)        # retired: must not count as low stock

    loan_a = borrow(app, u1, a, today=date(2020, 1, 1))  # long overdue
    borrow(app, u2, b, today=TODAY)                      # due in 14 days

    with app.app_context():
        s = admin_stats(get_db(), today=TODAY)
        assert (s["members"], s["books"], s["copies"]) == (2, 4, 8)   # admin is not a member
        assert (s["active"], s["overdue"]) == (2, 1)
        assert [r["title"] for r in s["low_stock"]] == ["Book B", "Book C"]

        return_book(get_db(), u1, loan_a)                # numbers follow the data
        s = admin_stats(get_db(), today=TODAY)
        assert (s["active"], s["overdue"]) == (1, 0)


def test_admin_dashboard_page_shows_live_numbers(client, app):
    add_book(app, "Scarce Book", total=1)
    login(client, "admin@test.com", "adminpass1")
    page = client.get("/admin/")
    assert page.status_code == 200
    assert b"Total members" in page.data and b"Scarce Book" in page.data


def test_member_dashboard_shows_only_own_loans_and_overdue(client, app):
    register(client)
    login(client)
    with app.app_context():
        me = get_db().execute("SELECT id FROM users WHERE email='member@test.com'").fetchone()["id"]
    other = add_user(app, "other@test.com")
    borrow(app, me, add_book(app, "My Late Book", total=2), today=date(2020, 1, 1))
    borrow(app, other, add_book(app, "Secret Book", total=2))

    page = client.get("/dashboard")
    assert b"My Late Book" in page.data and b"Overdue" in page.data
    assert b"1 of 3" in page.data
    assert b"Secret Book" not in page.data               # other members' loans stay private


def test_each_dashboard_is_restricted_to_its_role(client):
    register(client)
    login(client)
    assert client.get("/admin/").status_code == 403
    client.post("/logout")
    login(client, "admin@test.com", "adminpass1")
    assert client.get("/dashboard").status_code == 403
    assert client.get("/admin/").status_code == 200
