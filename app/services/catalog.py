"""Admin book management: validation and the transactions that keep copy counts consistent."""
import re
import sqlite3
from urllib.parse import urlparse

ISBN_RE = re.compile(r"^(?:[0-9]{13}|[0-9]{9}[0-9X])$")
INT_RE = re.compile(r"^-?[0-9]+$")
MAX_COPIES = 10000


class BookError(Exception):
    """A rule blocked the change; the message is safe to show to the admin."""


def clean_book_form(form):
    """Validate admin input. Returns (clean_values, error_messages)."""
    errors = []
    title = form.get("title", "").strip()
    author = form.get("author", "").strip()
    genre = form.get("category", "").strip()
    isbn = re.sub(r"[\s-]", "", form.get("isbn", "")).upper()
    description = form.get("description", "").strip()
    cover_url = form.get("cover_url", "").strip()
    total_raw = form.get("total_copies", "").strip()

    for label, value, limit in (("Title", title, 200), ("Author", author, 150), ("Genre", genre, 50)):
        if not value:
            errors.append(f"{label} is required.")
        elif len(value) > limit:
            errors.append(f"{label} must be at most {limit} characters.")
    if not isbn:
        errors.append("ISBN is required.")
    elif not ISBN_RE.match(isbn):
        errors.append("ISBN must be 10 or 13 digits (the last digit of a 10-digit ISBN may be X).")
    total = None
    if not INT_RE.match(total_raw):
        errors.append("Total copies must be a whole number.")
    else:
        total = int(total_raw)
        if total < 0:
            errors.append("Total copies cannot be negative.")
        elif total > MAX_COPIES:
            errors.append(f"Total copies cannot be more than {MAX_COPIES}.")
    if len(description) > 2000:
        errors.append("Description must be at most 2000 characters.")
    if cover_url:
        parts = urlparse(cover_url)
        if parts.scheme != "https" or not parts.netloc or len(cover_url) > 500:
            errors.append("Cover image must be an https:// link (500 characters at most).")

    clean = {"title": title, "author": author, "category": genre, "isbn": isbn,
             "description": description or None, "cover_url": cover_url or None,
             "total_copies": total}
    return clean, errors


def _rollback(db):
    if db.in_transaction:
        db.execute("ROLLBACK")


def add_book(db, clean):
    """New books start with every copy available."""
    try:
        cur = db.execute(
            "INSERT INTO books (title, author, isbn, category, cover_url, description, "
            "total_copies, available_copies) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (clean["title"], clean["author"], clean["isbn"], clean["category"], clean["cover_url"],
             clean["description"], clean["total_copies"], clean["total_copies"]))
    except sqlite3.IntegrityError as e:
        if "isbn" in str(e):
            raise BookError("A book with this ISBN already exists.")
        raise
    return cur.lastrowid


def update_book(db, book_id, clean):
    """Edit a book. Total copies may not drop below the number currently borrowed;
    available copies are recalculated as total minus borrowed. The count is read under
    the write lock, so a borrow cannot slip in between the check and the update."""
    db.execute("BEGIN IMMEDIATE")
    try:
        if db.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
            raise BookError("That book does not exist.")
        on_loan = db.execute(
            "SELECT COUNT(*) FROM borrowings WHERE book_id = ? AND returned_at IS NULL",
            (book_id,)).fetchone()[0]
        if clean["total_copies"] < on_loan:
            raise BookError(
                f"Total copies cannot be lower than the {on_loan} cop{'y' if on_loan == 1 else 'ies'} "
                "currently borrowed.")
        db.execute(
            "UPDATE books SET title = ?, author = ?, isbn = ?, category = ?, cover_url = ?, "
            "description = ?, total_copies = ?, available_copies = ? WHERE id = ?",
            (clean["title"], clean["author"], clean["isbn"], clean["category"], clean["cover_url"],
             clean["description"], clean["total_copies"], clean["total_copies"] - on_loan, book_id))
        db.execute("COMMIT")
    except sqlite3.IntegrityError as e:
        _rollback(db)
        if "isbn" in str(e):
            raise BookError("Another book already uses this ISBN.")
        raise
    except Exception:
        _rollback(db)
        raise
