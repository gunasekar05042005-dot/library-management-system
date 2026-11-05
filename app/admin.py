from flask import (Blueprint, abort, flash, redirect, render_template, request, url_for)

from .auth import admin_required
from .db import get_db
from .services.catalog import BookError, add_book, clean_book_form, update_book
from .services.pagination import page_info
from .services.reports import list_loans, members_overview
from .services.stats import admin_stats

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _genres(db):
    return [r["category"] for r in db.execute("SELECT DISTINCT category FROM books ORDER BY category")]


@bp.route("/")
@admin_required
def dashboard():
    return render_template("admin_dashboard.html", stats=admin_stats(get_db()))


@bp.route("/books")
@admin_required
def books():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    page, pages, offset, per = page_info(request.args, total)
    rows = db.execute("SELECT * FROM books ORDER BY title COLLATE NOCASE LIMIT ? OFFSET ?",
                      (per, offset)).fetchall()
    return render_template("admin_books.html", books=rows, total=total, page=page, pages=pages)


@bp.route("/books/new", methods=("GET", "POST"))
@admin_required
def new_book():
    db = get_db()
    form = {}
    if request.method == "POST":
        clean, errors = clean_book_form(request.form)
        if not errors:
            try:
                add_book(db, clean)
            except BookError as e:
                errors.append(str(e))
            else:
                flash(f"Added \u201c{clean['title']}\u201d.", "success")
                return redirect(url_for("admin.books"))
        for message in errors:
            flash(message, "error")
        form = request.form
    return render_template("book_form.html", form=form, book=None, on_loan=0, genres=_genres(db))


@bp.route("/books/<int:book_id>/edit", methods=("GET", "POST"))
@admin_required
def edit_book(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        abort(404)
    on_loan = db.execute("SELECT COUNT(*) FROM borrowings WHERE book_id = ? AND returned_at IS NULL",
                         (book_id,)).fetchone()[0]
    form = dict(book)
    if request.method == "POST":
        clean, errors = clean_book_form(request.form)
        if not errors:
            try:
                update_book(db, book_id, clean)
            except BookError as e:
                errors.append(str(e))
            else:
                flash("Book updated.", "success")
                return redirect(url_for("admin.books"))
        for message in errors:
            flash(message, "error")
        form = request.form
    return render_template("book_form.html", form=form, book=book, on_loan=on_loan, genres=_genres(db))


@bp.route("/members")
@admin_required
def members():
    rows, total, page, pages = members_overview(get_db(), request.args)
    return render_template("admin_members.html", members=rows, total=total, page=page, pages=pages)


@bp.route("/borrowings")
@admin_required
def borrowings():
    status = request.args.get("status", "")
    rows, total, page, pages = list_loans(get_db(), request.args, status=status)
    return render_template("admin_borrowings.html", loans=rows, total=total, page=page,
                           pages=pages, status=status)
