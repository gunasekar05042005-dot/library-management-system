from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .auth import login_required
from .db import get_db
from .services.borrowing import LOAN_DAYS, MAX_ACTIVE_LOANS, loan_status

bp = Blueprint("books", __name__)


@bp.route("/")
def home():
    return redirect(url_for("books.catalog"))


@bp.route("/books")
@login_required
def catalog():
    db = get_db()
    q = request.args.get("q", "").strip()
    genre = request.args.get("genre", "").strip()
    available_only = request.args.get("available") == "1"

    # The SQL text is built only from fixed fragments; user input always
    # travels as ? parameters, which prevents SQL injection.
    sql = "SELECT * FROM books WHERE 1 = 1"
    params = []
    if q:
        sql += " AND (title LIKE ? OR author LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if genre:
        sql += " AND category = ?"
        params.append(genre)
    if available_only:
        sql += " AND available_copies > 0"
    sql += " ORDER BY title COLLATE NOCASE"

    books = db.execute(sql, params).fetchall()
    genres = [r["category"] for r in
              db.execute("SELECT DISTINCT category FROM books ORDER BY category")]
    return render_template("catalog.html", books=books, genres=genres,
                           q=q, genre=genre, available_only=available_only)


@bp.route("/books/<int:book_id>")
@login_required
def detail(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        abort(404)
    status = loan_status(db, g.user["id"], book_id) if g.user["role"] == "member" else None
    return render_template("book_detail.html", book=book, status=status,
                           max_loans=MAX_ACTIVE_LOANS, loan_days=LOAN_DAYS)
