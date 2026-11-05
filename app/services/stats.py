"""Numbers for the admin dashboard. Every value is a live query, nothing is cached or sample data."""
from .clock import today as local_today

LOW_STOCK_THRESHOLD = 2   # "low availability" = this many copies available, or fewer


def _count(db, sql, *args):
    return db.execute(sql, args).fetchone()[0]


def admin_stats(db, today=None):
    today = (today or local_today()).isoformat()
    return {
        "members": _count(db, "SELECT COUNT(*) FROM users WHERE role = 'member'"),
        "books": _count(db, "SELECT COUNT(*) FROM books"),
        "copies": _count(db, "SELECT COALESCE(SUM(total_copies), 0) FROM books"),
        "active": _count(db, "SELECT COUNT(*) FROM borrowings WHERE returned_at IS NULL"),
        "overdue": _count(
            db, "SELECT COUNT(*) FROM borrowings WHERE returned_at IS NULL AND due_date < ?", today),
        # total_copies > 0 leaves out retired titles (0 copies owned), which are not "low stock".
        "low_stock": db.execute(
            "SELECT id, title, author, total_copies, available_copies FROM books "
            "WHERE total_copies > 0 AND available_copies <= ? "
            "ORDER BY available_copies, title COLLATE NOCASE", (LOW_STOCK_THRESHOLD,)).fetchall(),
        "threshold": LOW_STOCK_THRESHOLD,
    }
