"""All borrowing business rules live here, so routes stay thin and rules are testable."""
import sqlite3
from datetime import timedelta

from .clock import today as local_today

MAX_ACTIVE_LOANS = 3
LOAN_DAYS = 14


class BorrowError(Exception):
    """A business rule blocked the action. The message is safe to show to the member."""


class ReturnError(BorrowError):
    """A return was refused (record not found, or already returned)."""


def _rollback(db):
    if db.in_transaction:
        db.execute("ROLLBACK")


def borrow_book(db, user_id, book_id, today=None):
    """Borrow one copy. Returns (book_title, due_date). Raises BorrowError if a rule fails.

    BEGIN IMMEDIATE takes SQLite's write lock *before* any check is read. Two members
    trying to borrow at the same moment are therefore processed one after the other:
    the second one only starts reading after the first has committed, so it sees the
    updated copy count instead of a stale one.
    """
    today = today or local_today()
    due = today + timedelta(days=LOAN_DAYS)

    db.execute("BEGIN IMMEDIATE")
    try:
        book = db.execute(
            "SELECT title FROM books WHERE id = ?", (book_id,)).fetchone()
        if book is None:
            raise BorrowError("That book does not exist.")

        if db.execute(
            "SELECT 1 FROM borrowings WHERE user_id = ? AND book_id = ? AND returned_at IS NULL",
            (user_id, book_id),
        ).fetchone():
            raise BorrowError("You have already borrowed this book.")

        active = db.execute(
            "SELECT COUNT(*) FROM borrowings WHERE user_id = ? AND returned_at IS NULL",
            (user_id,),
        ).fetchone()[0]
        if active >= MAX_ACTIVE_LOANS:
            raise BorrowError(
                f"You can borrow at most {MAX_ACTIVE_LOANS} books at a time. "
                "Return one before borrowing another.")

        # Check-and-decrement in ONE statement: it only succeeds if a copy is left.
        taken = db.execute(
            "UPDATE books SET available_copies = available_copies - 1 "
            "WHERE id = ? AND available_copies > 0", (book_id,))
        if taken.rowcount != 1:
            raise BorrowError("No copies of this book are available right now.")

        db.execute(
            "INSERT INTO borrowings (user_id, book_id, borrowed_at, due_date) VALUES (?, ?, ?, ?)",
            (user_id, book_id, today.isoformat(), due.isoformat()))
        db.execute("COMMIT")                 # copy count and loan record become visible together
    except sqlite3.IntegrityError as e:
        _rollback(db)
        if "UNIQUE" in str(e):               # the unique index fired: duplicate active loan
            raise BorrowError("You have already borrowed this book.")
        raise                                # anything else is a genuine fault: do not disguise it
    except Exception:
        _rollback(db)                        # undo everything, including the copy decrement
        raise
    return book["title"], due


def loan_status(db, user_id, book_id):
    """Used by the book page to show the right button (the rules above still decide)."""
    loan = db.execute(
        "SELECT due_date FROM borrowings WHERE user_id = ? AND book_id = ? AND returned_at IS NULL",
        (user_id, book_id)).fetchone()
    active = db.execute(
        "SELECT COUNT(*) FROM borrowings WHERE user_id = ? AND returned_at IS NULL",
        (user_id,)).fetchone()[0]
    return {"loan": loan, "at_limit": active >= MAX_ACTIVE_LOANS}


def return_book(db, user_id, borrowing_id, today=None):
    """Return a borrowed book. Returns the book title. Raises ReturnError if refused.

    Same pattern as borrowing: BEGIN IMMEDIATE, then one transaction that closes the
    loan AND gives the copy back. Either both changes happen or neither does.
    """
    today = today or local_today()

    db.execute("BEGIN IMMEDIATE")
    try:
        # Filtering by user_id means a member can only ever touch their own loans.
        # Someone else's loan gets the same "not found" answer as a made-up ID.
        loan = db.execute(
            "SELECT br.book_id, br.borrowed_at, bk.title FROM borrowings br "
            "JOIN books bk ON bk.id = br.book_id "
            "WHERE br.id = ? AND br.user_id = ?", (borrowing_id, user_id)).fetchone()
        if loan is None:
            raise ReturnError("Borrowing record not found.")

        # Never record a return date earlier than the borrow date (clock or timezone shifts
        # would otherwise violate the table's CHECK and leave the loan impossible to close).
        returned_on = max(today.isoformat(), loan["borrowed_at"])

        # Close the loan only if it is still open. If it was already returned,
        # zero rows change and we stop BEFORE touching the copy count.
        closed = db.execute(
            "UPDATE borrowings SET returned_at = ? "
            "WHERE id = ? AND user_id = ? AND returned_at IS NULL",
            (returned_on, borrowing_id, user_id))
        if closed.rowcount != 1:
            raise ReturnError("This book has already been returned.")

        db.execute(
            "UPDATE books SET available_copies = available_copies + 1 WHERE id = ?",
            (loan["book_id"],))
        db.execute("COMMIT")
    except Exception:
        _rollback(db)
        raise
    return loan["title"]


def current_loans(db, user_id, today=None):
    """A member's active loans, soonest due first. is_overdue is 1 when past the due date."""
    today = today or local_today()
    return db.execute(
        "SELECT br.id, br.borrowed_at, br.due_date, (br.due_date < ?) AS is_overdue, "
        "       bk.id AS book_id, bk.title, bk.author, bk.cover_url "
        "FROM borrowings br JOIN books bk ON bk.id = br.book_id "
        "WHERE br.user_id = ? AND br.returned_at IS NULL "
        "ORDER BY br.due_date", (today.isoformat(), user_id)).fetchall()
