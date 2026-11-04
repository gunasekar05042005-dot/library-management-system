import functools
import re
import sqlite3
from urllib.parse import urlparse

import click
from flask import (Blueprint, abort, current_app, flash, g, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_PASSWORD_LENGTH = 128  # stops absurdly long inputs from slowing down hashing


# ---------- validation ----------
def validate_registration(full_name, email, password, confirm=None):
    """Return a list of error messages (empty list = valid)."""
    errors = []
    if not full_name:
        errors.append("Full name is required.")
    if not EMAIL_RE.match(email):
        errors.append("Enter a valid email address.")
    min_len = current_app.config["MIN_PASSWORD_LENGTH"]
    if len(password) < min_len:
        errors.append(f"Password must be at least {min_len} characters.")
    elif len(password) > MAX_PASSWORD_LENGTH:
        errors.append(f"Password must be at most {MAX_PASSWORD_LENGTH} characters.")
    if confirm is not None and password != confirm:
        errors.append("Passwords do not match.")
    return errors


def email_exists(email):
    row = get_db().execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
    return row is not None


def create_user(full_name, email, password, role="member"):
    """Insert a user. The UNIQUE constraint is the final guard against duplicates."""
    db = get_db()
    db.execute(
        "INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (full_name, email, generate_password_hash(password), role),
    )
    db.commit()


def safe_next(target):
    """Allow redirects only to paths on this site (prevents open-redirect attacks)."""
    if not target:
        return None
    parts = urlparse(target)
    if (parts.scheme or parts.netloc or not target.startswith("/")
            or target.startswith("//") or "\\" in target):
        return None
    return target


# ---------- who is logged in? ----------
@bp.before_app_request
def load_logged_in_user():
    """Runs before every request: look up the user from the session on every request."""
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = get_db().execute(
            "SELECT id, full_name, email, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if g.user is None:  # account no longer exists
            session.clear()


# ---------- access control decorators ----------
def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "info")
            target = request.full_path if request.query_string else request.path
            return redirect(url_for("auth.login", next=target))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @login_required                      # 1st: must be logged in
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user["role"] != "admin":    # 2nd: must be an admin
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def member_required(view):
    @login_required
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user["role"] != "member":   # borrowing is a member action
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# ---------- routes ----------
@bp.route("/register", methods=("GET", "POST"))
def register():
    if g.user:
        return redirect(url_for("books.catalog"))

    form = {"full_name": "", "email": ""}
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = validate_registration(full_name, email, password, confirm)
        if not errors and email_exists(email):
            errors.append("An account with this email already exists.")
        if not errors:
            try:
                create_user(full_name, email, password)  # role is ALWAYS 'member' here
            except sqlite3.IntegrityError:               # two sign-ups racing for one email
                errors.append("An account with this email already exists.")
            else:
                flash("Account created. You can log in now.", "success")
                return redirect(url_for("auth.login"))

        for message in errors:
            flash(message, "error")
        form = {"full_name": full_name, "email": email}

    return render_template("register.html", form=form,
                           min_length=current_app.config["MIN_PASSWORD_LENGTH"])


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("books.catalog"))

    next_url = request.values.get("next", "")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        # One generic message, so attackers can't tell which emails are registered.
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
        else:
            session.clear()                   # new session on login (prevents session fixation)
            session["user_id"] = user["id"]   # store only the id; role is re-read each request
            session.permanent = True
            default = "admin.dashboard" if user["role"] == "admin" else "books.catalog"
            return redirect(safe_next(next_url) or url_for(default))

    return render_template("login.html", next_url=next_url)


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ---------- CLI: the only way to create an admin ----------
@click.command("create-admin")
@click.option("--name", prompt="Full name")
@click.option("--email", prompt="Email")
@click.password_option()
def create_admin_command(name, email, password):
    """Create an administrator account."""
    name, email = name.strip(), email.strip().lower()
    errors = validate_registration(name, email, password)
    if not errors and email_exists(email):
        errors.append("An account with this email already exists.")
    if errors:
        raise click.ClickException(" ".join(errors))
    create_user(name, email, password, role="admin")
    click.echo(f"Admin account created for {email}.")
