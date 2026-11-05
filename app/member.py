import sqlite3

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .auth import member_required
from .db import get_db
from .services.borrowing import (MAX_ACTIVE_LOANS, BorrowError, ReturnError,
                                 borrow_book, current_loans, return_book)
from .services.reports import list_loans

bp = Blueprint("member", __name__)

BUSY = "The library is busy right now. Please try again."


@bp.route("/borrow/<int:book_id>", methods=("POST",))
@member_required
def borrow(book_id):
    try:
        title, due = borrow_book(get_db(), g.user["id"], book_id)
    except BorrowError as e:
        flash(str(e), "error")
    except sqlite3.OperationalError:         # e.g. database stayed locked past the timeout
        flash(BUSY, "error")
    else:
        flash(f"You borrowed \u201c{title}\u201d. Please return it by {due.isoformat()}.", "success")
    return redirect(url_for("books.detail", book_id=book_id))


@bp.route("/dashboard")
@member_required
def dashboard():
    loans = current_loans(get_db(), g.user["id"])   # only this member's loans, soonest due first
    overdue = sum(1 for loan in loans if loan["is_overdue"])
    return render_template("member_dashboard.html", loans=loans, overdue=overdue,
                           max_loans=MAX_ACTIVE_LOANS)


@bp.route("/return/<int:borrowing_id>", methods=("POST",))
@member_required
def return_loan(borrowing_id):
    try:
        title = return_book(get_db(), g.user["id"], borrowing_id)
    except ReturnError as e:
        flash(str(e), "error")
    except sqlite3.OperationalError:
        flash(BUSY, "error")
    else:
        flash(f"You returned \u201c{title}\u201d. Thank you!", "success")
    return redirect(url_for("member.dashboard"))


@bp.route("/history")
@member_required
def history():
    # user_id always comes from the session, never from the URL (BR-05).
    loans, total, page, pages = list_loans(get_db(), request.args, user_id=g.user["id"],
                                           status=request.args.get("status"))
    return render_template("history.html", loans=loans, total=total, page=page, pages=pages,
                           status=request.args.get("status", ""))
