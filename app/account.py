import re

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .auth import MAX_NAME_LENGTH, login_required
from .db import get_db

bp = Blueprint("account", __name__)
PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-]{5,18}[0-9]$")


@bp.route("/profile", methods=("GET", "POST"))
@login_required
def profile():
    """Members and admins can view and update their own name and phone.
    Email and role are never read from the form, so they cannot be changed here."""
    db = get_db()
    form = {"full_name": g.user["full_name"], "phone": g.user["phone"] or ""}
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        errors = []
        if not full_name:
            errors.append("Full name is required.")
        elif len(full_name) > MAX_NAME_LENGTH:
            errors.append(f"Full name must be at most {MAX_NAME_LENGTH} characters.")
        if phone and not PHONE_RE.match(phone):
            errors.append("Enter a valid phone number (digits, spaces or dashes, optional leading +).")
        if not errors:
            db.execute("UPDATE users SET full_name = ?, phone = ? WHERE id = ?",
                       (full_name, phone or None, g.user["id"]))
            flash("Profile updated.", "success")
            return redirect(url_for("account.profile"))
        for message in errors:
            flash(message, "error")
        form = {"full_name": full_name, "phone": phone}
    since = db.execute("SELECT created_at FROM users WHERE id = ?", (g.user["id"],)).fetchone()[0][:10]
    return render_template("profile.html", form=form, member_since=since)
