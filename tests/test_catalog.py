"""Book catalog: search, filters, pagination, details, default cover."""
import re

import pytest

from app.db import get_db
from tests.test_edge_cases import member_client


def found(resp):
    return int(re.search(rb"(\d+) books? found", resp.data).group(1))


def add(app, title, author, genre="Programming", total=2, available=None, description=None):
    with app.app_context():
        get_db().execute(
            "INSERT INTO books (title, author, category, total_copies, available_copies, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, author, genre, total, total if available is None else available, description))


@pytest.fixture
def library(app):
    add(app, "Python Basics", "Alice Smith")
    add(app, "Advanced Python", "Carol Stone")
    add(app, "Cooking 101", "Bob Stone", genre="Food", total=1, available=0)
    return app


def test_search_by_title_is_case_insensitive(library):
    resp = member_client(library, "m@test.com").get("/books", query_string={"q": "PYTHON"})
    assert found(resp) == 2 and b"Cooking 101" not in resp.data


def test_search_by_author(library):
    resp = member_client(library, "m@test.com").get("/books", query_string={"q": "stone"})
    assert found(resp) == 2 and b"Advanced Python" in resp.data and b"Cooking 101" in resp.data


def test_filter_by_genre(library):
    resp = member_client(library, "m@test.com").get("/books", query_string={"genre": "Food"})
    assert found(resp) == 1 and b"Cooking 101" in resp.data


def test_search_and_genre_combine(library):
    resp = member_client(library, "m@test.com").get("/books", query_string={"q": "stone", "genre": "Programming"})
    assert found(resp) == 1 and b"Advanced Python" in resp.data


def test_available_now_filter_hides_books_with_no_copies(library):
    resp = member_client(library, "m@test.com").get("/books", query_string={"available": "1"})
    assert found(resp) == 2 and b"Cooking 101" not in resp.data


def test_no_match_shows_a_friendly_message(library):
    resp = member_client(library, "m@test.com").get("/books", query_string={"q": "zzzz"})
    assert found(resp) == 0 and b"No books match" in resp.data


def test_percent_and_underscore_are_searched_literally(app):
    add(app, "100% Juice", "Fruit Press")
    add(app, "Plain Book", "Someone")
    c = member_client(app, "m@test.com")
    assert found(c.get("/books", query_string={"q": "%"})) == 1      # only the title containing %
    assert found(c.get("/books", query_string={"q": "_"})) == 0      # no wildcard match-everything
    assert found(c.get("/books", query_string={"q": "100%"})) == 1


def test_catalog_is_paginated_and_clamps_bad_page_numbers(app):
    for i in range(30):
        add(app, f"Book {i:02d}", "Author")
    c = member_client(app, "m@test.com")
    page1 = c.get("/books", query_string={"q": "Book"})
    assert found(page1) == 30 and page1.data.count(b'class="book"') == 12
    assert b"Page 1 of 3" in page1.data and b"page=2" in page1.data
    assert c.get("/books", query_string={"q": "Book", "page": 3}).data.count(b'class="book"') == 6
    assert b"Page 3 of 3" in c.get("/books", query_string={"page": 999}).data
    assert b"Page 1 of 3" in c.get("/books", query_string={"page": "abc"}).data


def test_details_page_shows_description_and_default_cover(app):
    add(app, "Described Book", "Author", description="A short summary of the book.")
    c = member_client(app, "m@test.com")
    with app.app_context():
        bid = get_db().execute("SELECT id FROM books").fetchone()["id"]
    page = c.get(f"/books/{bid}")
    assert b"A short summary of the book." in page.data and b"default-cover.svg" in page.data
    catalog = c.get("/books")
    assert b"data-fallback" in catalog.data and b"onerror" not in catalog.data   # CSP-friendly


def test_catalog_requires_login(client):
    resp = client.get("/books")
    assert resp.status_code == 302 and "next=" in resp.headers["Location"]
