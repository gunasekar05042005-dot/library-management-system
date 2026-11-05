from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from .auth import login_required
from .db import get_db
from .services.borrowing import LOAN_DAYS, MAX_ACTIVE_LOANS, loan_status
from .services.pagination import page_info

bp = Blueprint("books", __name__)
PER_PAGE = 12


def like_pattern(text):
    """Escape % and _ so they are searched literally instead of acting as wildcards."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@bp.route("/")
def home():
    return redirect(url_for("books.catalog"))


@bp.route("/books")
@login_required
def catalog():
    db = get_db()
    q = request.args.get("q", "").strip()[:100]
    genre = request.args.get("genre", "").strip()[:100]
    available_only = request.args.get("available") == "1"

    # The SQL text is built only from fixed fragments; user input always
    # travels as ? parameters, which prevents SQL injection.
    where, params = ["1 = 1"], []
    if q:
        where.append("(title LIKE ? ESCAPE '\\' OR author LIKE ? ESCAPE '\\')")
        params += [like_pattern(q), like_pattern(q)]
    if genre:
        where.append("category = ?")
        params.append(genre)
    if available_only:
        where.append("available_copies > 0")
    where_sql = " AND ".join(where)

    total = db.execute(f"SELECT COUNT(*) FROM books WHERE {where_sql}", params).fetchone()[0]
    page, pages, offset, per = page_info(request.args, total, PER_PAGE)
    books = db.execute(
        f"SELECT * FROM books WHERE {where_sql} ORDER BY title COLLATE NOCASE LIMIT ? OFFSET ?",
        params + [per, offset]).fetchall()
    genres = [r["category"] for r in
              db.execute("SELECT DISTINCT category FROM books ORDER BY category")]
    return render_template("catalog.html", books=books, genres=genres, q=q, genre=genre,
                           available_only=available_only, total=total, page=page, pages=pages)


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
