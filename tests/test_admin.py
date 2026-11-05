"""Admin: add/edit books (BR-06), the total-copies rule, member and borrowing lists."""
import threading
from datetime import date

import pytest

from app.db import connect, get_db
from app.services.borrowing import BorrowError, borrow_book
from app.services.catalog import BookError, update_book
from tests.conftest import admin_client, uid_of
from tests.test_borrowing import add_book, add_user
from tests.test_edge_cases import member_client
from tests.test_returning import borrow

GOOD = {"title": "New Book", "author": "An Author", "category": "Science", "isbn": "9781234567897",
        "total_copies": "3", "cover_url": "", "description": "A description."}


def book_row(app, isbn="9781234567897"):
    with app.app_context():
        return get_db().execute("SELECT * FROM books WHERE isbn = ?", (isbn,)).fetchone()


def book_count(app):
    with app.app_context():
        return get_db().execute("SELECT COUNT(*) FROM books").fetchone()[0]


# ---------- permissions (BR-06) ----------
@pytest.mark.parametrize("path", ["/admin/books", "/admin/books/new", "/admin/members", "/admin/borrowings"])
def test_admin_pages_need_an_admin(app, client, path):
    assert "/login" in client.get(path).headers["Location"]
    assert member_client(app, "m@test.com").get(path).status_code == 403


def test_member_cannot_add_or_edit_books_even_with_a_forged_post(app):
    bid = add_book(app, total=2)
    member = member_client(app, "m@test.com")
    assert member.post("/admin/books/new", data=GOOD).status_code == 403
    assert member.post(f"/admin/books/{bid}/edit", data={**GOOD, "title": "Hacked"}).status_code == 403
    assert book_count(app) == 1
    with app.app_context():
        assert get_db().execute("SELECT title FROM books WHERE id = ?", (bid,)).fetchone()[0] == "Book"


# ---------- add ----------
def test_admin_adds_a_book_with_every_copy_available(app):
    resp = admin_client(app).post("/admin/books/new", data=GOOD)
    assert resp.status_code == 302
    row = book_row(app)
    assert (row["total_copies"], row["available_copies"]) == (3, 3)
    assert row["description"] == "A description." and row["cover_url"] is None
    assert b"New Book" in member_client(app, "m@test.com").get("/books").data


def test_isbn_is_normalised_and_cover_link_stored(app):
    admin_client(app).post("/admin/books/new", data={**GOOD, "isbn": "978-1-234-56789-7",
                                                      "cover_url": "https://example.com/c.jpg"})
    assert book_row(app)["cover_url"] == "https://example.com/c.jpg"


def test_isbn10_with_x_and_zero_copies_are_accepted(app):
    admin_client(app).post("/admin/books/new", data={**GOOD, "isbn": "097522980x", "total_copies": "0"})
    assert book_row(app, "097522980X")["total_copies"] == 0


@pytest.mark.parametrize("change,message", [
    ({"title": ""}, b"Title is required"), ({"author": " "}, b"Author is required"),
    ({"category": ""}, b"Genre is required"), ({"isbn": ""}, b"ISBN is required"),
    ({"isbn": "123"}, b"ISBN must be"), ({"isbn": "97812345678AB"}, b"ISBN must be"),
    ({"total_copies": ""}, b"whole number"), ({"total_copies": "abc"}, b"whole number"),
    ({"total_copies": "1.5"}, b"whole number"), ({"total_copies": "-1"}, b"cannot be negative"),
    ({"total_copies": "10001"}, b"more than 10000"), ({"title": "T" * 201}, b"at most 200"),
    ({"cover_url": "http://x.com/a.jpg"}, b"https://"), ({"cover_url": "javascript:alert(1)"}, b"https://"),
    ({"description": "D" * 2001}, b"at most 2000"),
])
def test_invalid_book_data_is_rejected(app, change, message):
    resp = admin_client(app).post("/admin/books/new", data={**GOOD, **change})
    assert resp.status_code == 200 and message in resp.data
    assert book_count(app) == 0


def test_isbn_must_be_unique(app):
    admin = admin_client(app)
    admin.post("/admin/books/new", data=GOOD)
    for isbn in ("9781234567897", "978-1-234-56789-7"):
        resp = admin.post("/admin/books/new", data={**GOOD, "title": "Copycat", "isbn": isbn})
        assert b"already exists" in resp.data
    assert book_count(app) == 1


# ---------- edit and the total-copies rule ----------
def test_total_copies_cannot_drop_below_the_borrowed_count(app):
    admin = admin_client(app)
    admin.post("/admin/books/new", data=GOOD)
    bid = book_row(app)["id"]
    borrow(app, add_user(app, "a@test.com"), bid)
    borrow(app, add_user(app, "b@test.com"), bid)              # 2 of 3 copies are out

    edit = lambda **c: admin.post(f"/admin/books/{bid}/edit", data={**GOOD, **c})
    assert edit(total_copies="5", title="Renamed").status_code == 302
    row = book_row(app)
    assert (row["title"], row["total_copies"], row["available_copies"]) == ("Renamed", 5, 3)

    assert edit(total_copies="2", title="Renamed").status_code == 302   # exactly the borrowed count: allowed
    assert book_row(app)["available_copies"] == 0

    rejected = edit(total_copies="1", title="Should not apply")
    assert rejected.status_code == 200 and b"cannot be lower than the 2 copies currently borrowed" in rejected.data
    row = book_row(app)
    assert (row["title"], row["total_copies"], row["available_copies"]) == ("Renamed", 2, 0)
    assert row["available_copies"] <= row["total_copies"]


def test_edit_checks_isbn_against_other_books_only(app):
    admin = admin_client(app)
    admin.post("/admin/books/new", data=GOOD)
    admin.post("/admin/books/new", data={**GOOD, "title": "Second", "isbn": "9780000000002"})
    second = book_row(app, "9780000000002")["id"]
    clash = admin.post(f"/admin/books/{second}/edit", data={**GOOD, "title": "Second"})
    assert b"Another book already uses this ISBN" in clash.data
    own = admin.post(f"/admin/books/{second}/edit", data={**GOOD, "title": "Second", "isbn": "9780000000002"})
    assert own.status_code == 302                              # keeping its own ISBN is fine


def test_edit_form_is_prefilled_and_missing_books_give_404(app):
    admin = admin_client(app)
    bid = add_book(app, "Prefilled", total=2)
    borrow(app, add_user(app, "a@test.com"), bid)
    page = admin.get(f"/admin/books/{bid}/edit")
    assert b"Prefilled" in page.data and b"currently borrowed" in page.data
    assert admin.get("/admin/books/9999/edit").status_code == 404
    assert admin.post("/admin/books/9999/edit", data=GOOD).status_code == 404


def test_edit_and_borrow_racing_never_break_the_copy_counts(app):
    uid = add_user(app, "a@test.com")
    for attempt in range(6):
        bid = add_book(app, f"Race {attempt}", total=1)
        clean = {"title": "T", "author": "A", "category": "C", "isbn": f"97800000001{attempt:02d}",
                 "description": None, "cover_url": None, "total_copies": 0}
        barrier = threading.Barrier(2)

        def borrowing():
            db = connect(app.config["DATABASE"])
            try:
                barrier.wait()
                borrow_book(db, uid, bid)
            except BorrowError:
                pass
            finally:
                db.close()

        def editing():
            db = connect(app.config["DATABASE"])
            try:
                barrier.wait()
                update_book(db, bid, clean)
            except BookError:
                pass
            finally:
                db.close()

        threads = [threading.Thread(target=borrowing), threading.Thread(target=editing)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        with app.app_context():
            db = get_db()
            total, available = db.execute("SELECT total_copies, available_copies FROM books WHERE id=?", (bid,)).fetchone()
            on_loan = db.execute("SELECT COUNT(*) FROM borrowings WHERE book_id=? AND returned_at IS NULL", (bid,)).fetchone()[0]
        assert available >= 0 and available <= total and available + on_loan == total


# ---------- admin lists ----------
def test_members_list_shows_members_only_with_counts(app):
    a, b = add_user(app, "a@test.com"), add_user(app, "b@test.com")
    borrow(app, a, add_book(app, "Old Book", total=2), today=date(2020, 1, 1))
    page = admin_client(app).get("/admin/members")
    assert b"a@test.com" in page.data and b"b@test.com" in page.data
    assert b"admin@test.com" not in page.data                  # admins are not members
    assert b'badge overdue">1</span>' in page.data


def test_borrowings_list_filters_and_names_the_member(app):
    a = add_user(app, "a@test.com")
    borrow(app, a, add_book(app, "Old Book", total=2), today=date(2020, 1, 1))
    borrow(app, a, add_book(app, "New Book", total=2))
    admin = admin_client(app)
    everything = admin.get("/admin/borrowings")
    assert b"Old Book" in everything.data and b"New Book" in everything.data and b"a@test.com" in everything.data
    overdue = admin.get("/admin/borrowings", query_string={"status": "overdue"})
    assert b"Old Book" in overdue.data and b"New Book" not in overdue.data
