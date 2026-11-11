import functools
import hashlib
import re
import sqlite3
from urllib.parse import urlparse

import click
from flask import (Blueprint, abort, current_app, flash, g, redirect,
                   render_template, request, session, url_for)
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 254
MAX_PASSWORD_LENGTH = 128  # stops absurdly long inputs from slowing down hashing
# Checked when an email is unknown, so rejecting an unknown email takes as long as a wrong password.
DUMMY_HASH = generate_password_hash("not-a-real-password")


# ---------- validation ----------
def validate_password(password, confirm=None):
    errors = []
    min_len = current_app.config["MIN_PASSWORD_LENGTH"]
    if not password:
        errors.append("Password is required.")
    elif len(password) < min_len:
        errors.append(f"Password must be at least {min_len} characters.")
    elif len(password) > MAX_PASSWORD_LENGTH:
        errors.append(f"Password must be at most {MAX_PASSWORD_LENGTH} characters.")
    if confirm is not None and password != confirm:
        errors.append("Passwords do not match.")
    return errors


def validate_registration(full_name, email, password, confirm=None):
    """Return a list of error messages (empty list = valid)."""
    errors = []
    if not full_name:
        errors.append("Full name is required.")
    elif len(full_name) > MAX_NAME_LENGTH:
        errors.append(f"Full name must be at most {MAX_NAME_LENGTH} characters.")
    if not email:
        errors.append("Email is required.")
    elif not EMAIL_RE.match(email) or len(email) > MAX_EMAIL_LENGTH:
        errors.append("Enter a valid email address.")
    return errors + validate_password(password, confirm)


def email_exists(email):
    return get_db().execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone() is not None


def create_user(full_name, email, password, role="member"):
    """Insert a user. The UNIQUE constraint is the final guard against duplicates."""
    db = get_db()
    db.execute(
        "INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (full_name, email, generate_password_hash(password), role))
    db.commit()


def fingerprint(password_hash):
    """Short digest of the stored hash. It changes whenever the password changes, which
    ends old sessions and makes password-reset links single-use."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


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
    """Runs before every page request: rebuild the user from the session and the database."""
    g.user = None
    if request.endpoint == "static":          # CSS/JS files need no user lookup
        return
    user_id = session.get("user_id")
    if user_id is None:
        return
    row = get_db().execute(
        "SELECT id, full_name, email, phone, role, password_hash FROM users WHERE id = ?",
        (user_id,)).fetchone()
    # Reject sessions for deleted accounts, and sessions that began before the last password
    # change (also rejects cookies that were forged without knowing the password hash).
    if row is None or session.get("pw_fp") != fingerprint(row["password_hash"]):
        session.clear()
        return
    g.user = {key: row[key] for key in ("id", "full_name", "email", "phone", "role")}


# ---------- access control decorators ----------
def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "info")
            if request.method in ("GET", "HEAD"):   # only a page view can be resumed after login
                target = request.full_path if request.query_string else request.path
                return redirect(url_for("auth.login", next=target))
            return redirect(url_for("auth.login"))
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


def _authenticate(require_admin=False):
    """Check the submitted email and password. On success start a fresh session and return the
    user; otherwise return None. One hash check always runs, so response time does not reveal
    which emails exist, and a member's password is never accepted on the admin page."""
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    stored = user["password_hash"] if user else DUMMY_HASH
    password_ok = check_password_hash(stored, password)
    if user is None or not password_ok or (require_admin and user["role"] != "admin"):
        return None
    session.clear()                       # new session on login (prevents session fixation)
    session["user_id"] = user["id"]       # the role is re-read from the database each request
    session["pw_fp"] = fingerprint(user["password_hash"])
    session.permanent = True
    return user


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
        user = _authenticate()
        # One generic message, so attackers can't tell which emails are registered.
        if user is None:
            flash("Invalid email or password.", "error")
        else:
            default = "admin.dashboard" if user["role"] == "admin" else "books.catalog"
            return redirect(safe_next(next_url) or url_for(default))

    return render_template("login.html", next_url=next_url)


@bp.route("/admin/login", methods=("GET", "POST"))
def admin_login():
    """A separate, clearly labelled sign-in for administrators. Only admin accounts get in."""
    if g.user:
        return redirect(url_for("admin.dashboard" if g.user["role"] == "admin" else "books.catalog"))
    if request.method == "POST":
        if _authenticate(require_admin=True):
            return redirect(url_for("admin.dashboard"))
        flash("Invalid administrator email or password.", "error")
    return render_template("admin_login.html")


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ---------- password reset ----------
# No email server is configured, so the link is written to the server log (and shown on the
# page only when SHOW_RESET_LINK is on). The token is signed, expires, and dies after one use.
def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")


def make_reset_token(user):
    return _serializer().dumps({"uid": user["id"], "fp": fingerprint(user["password_hash"])})


def read_reset_token(token):
    """Return the user if the token is genuine, unexpired and unused; otherwise None."""
    try:
        data = _serializer().loads(token, max_age=current_app.config["RESET_TOKEN_MAX_AGE"])
        user = get_db().execute("SELECT * FROM users WHERE id = ?", (data["uid"],)).fetchone()
        used_up = user is None or data["fp"] != fingerprint(user["password_hash"])
    except (BadSignature, KeyError, TypeError):   # an expired token is a BadSignature too
        return None
    return None if used_up else user


@bp.route("/forgot-password", methods=("GET", "POST"))
def forgot_password():
    link = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            link = url_for("auth.reset_password", token=make_reset_token(user), _external=True)
            current_app.logger.warning("Password reset link for %s: %s", email, link)
        # The same message either way, so this page cannot be used to find registered emails.
        flash("If that email is registered, a password reset link has been sent.", "info")
        if not current_app.config["SHOW_RESET_LINK"]:
            link = None
    return render_template("forgot_password.html", link=link)


@bp.route("/reset-password/<token>", methods=("GET", "POST"))
def reset_password(token):
    user = read_reset_token(token)
    if user is None:
        flash("This reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        errors = validate_password(password, request.form.get("confirm_password", ""))
        if not errors:
            db = get_db()
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                       (generate_password_hash(password), user["id"]))
            db.commit()
            session.clear()
            flash("Password updated. Please log in with your new password.", "success")
            return redirect(url_for("auth.login"))
        for message in errors:
            flash(message, "error")
    return render_template("reset_password.html", min_length=current_app.config["MIN_PASSWORD_LENGTH"])


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
