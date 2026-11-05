"""Read-only listings used by the member history and the admin pages."""
from .clock import today as local_today
from .pagination import page_info

# Status is derived, never stored, so it cannot go stale.
STATUS_SQL = ("CASE WHEN br.returned_at IS NOT NULL THEN 'Returned' "
              "WHEN br.due_date < :today THEN 'Overdue' ELSE 'Borrowed' END")
FILTERS = {
    "borrowed": "br.returned_at IS NULL AND br.due_date >= :today",
    "overdue": "br.returned_at IS NULL AND br.due_date < :today",
    "returned": "br.returned_at IS NOT NULL",
}


def list_loans(db, args, user_id=None, status=None, today=None):
    """Borrowing records, newest first. Pass user_id to restrict to one member (BR-05)."""
    today = (today or local_today()).isoformat()
    where, params = ["1 = 1"], {"today": today}
    if user_id is not None:
        where.append("br.user_id = :uid")
        params["uid"] = user_id
    if status in FILTERS:
        where.append(FILTERS[status])
    base = ("FROM borrowings br JOIN users u ON u.id = br.user_id "
            "JOIN books bk ON bk.id = br.book_id WHERE " + " AND ".join(where))
    total = db.execute("SELECT COUNT(*) " + base, params).fetchone()[0]
    page, pages, offset, per = page_info(args, total)
    rows = db.execute(
        "SELECT br.id, br.borrowed_at, br.due_date, br.returned_at, " + STATUS_SQL + " AS status, "
        "bk.id AS book_id, bk.title, bk.author, u.full_name, u.email " + base +
        " ORDER BY br.borrowed_at DESC, br.id DESC LIMIT :per OFFSET :off",
        {**params, "per": per, "off": offset}).fetchall()
    return rows, total, page, pages


def members_overview(db, args, today=None):
    today = (today or local_today()).isoformat()
    total = db.execute("SELECT COUNT(*) FROM users WHERE role = 'member'").fetchone()[0]
    page, pages, offset, per = page_info(args, total)
    rows = db.execute(
        "SELECT u.id, u.full_name, u.email, u.phone, u.created_at, "
        " (SELECT COUNT(*) FROM borrowings b WHERE b.user_id = u.id AND b.returned_at IS NULL) AS active, "
        " (SELECT COUNT(*) FROM borrowings b WHERE b.user_id = u.id AND b.returned_at IS NULL "
        "    AND b.due_date < :today) AS overdue "
        "FROM users u WHERE u.role = 'member' ORDER BY u.full_name COLLATE NOCASE "
        "LIMIT :per OFFSET :off", {"today": today, "per": per, "off": offset}).fetchall()
    return rows, total, page, pages
