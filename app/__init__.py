import os
import secrets
from datetime import timedelta

from flask import Flask, render_template

from . import account, admin, auth, books, db, member, security


def _load_secret_key(app):
    """SECRET_KEY from the environment, otherwise a random key created once and kept in
    instance/secret.key. There is no hard-coded default that could be looked up in the source."""
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    path = os.path.join(app.instance_path, "secret.key")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    with open(path) as f:
        return f.read().strip()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=_load_secret_key(app),
        DATABASE=os.path.join(app.instance_path, "library.sqlite"),
        TIMEZONE=os.environ.get("LIBRARY_TIMEZONE", "Asia/Kolkata"),
        MIN_PASSWORD_LENGTH=8,
        CSRF_ENABLED=True,
        MAX_CONTENT_LENGTH=64 * 1024,            # reject oversized request bodies
        RESET_TOKEN_MAX_AGE=3600,                # password-reset links last one hour
        SHOW_RESET_LINK=os.environ.get("SHOW_RESET_LINK") == "1" or app.debug,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_REFRESH_EACH_REQUEST=False,      # 8 hours from login, not from last click
        SESSION_COOKIE_HTTPONLY=True,            # JavaScript cannot read the session cookie
        SESSION_COOKIE_SAMESITE="Lax",           # not sent on cross-site POSTs
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",  # set to 1 behind HTTPS
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    security.init_app(app)
    app.cli.add_command(auth.create_admin_command)
    for blueprint in (auth.bp, books.bp, member.bp, account.bp, admin.bp):
        app.register_blueprint(blueprint)

    titles = {400: "Request not accepted", 403: "Access denied", 404: "Page not found",
              405: "Method not allowed", 413: "Request too large", 500: "Something went wrong"}

    def error_page(e):
        return render_template("error.html", code=e.code, title=titles[e.code],
                               message=e.description), e.code

    for code in titles:
        app.register_error_handler(code, error_page)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")          # no clickjacking
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' https: data:; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        return response

    return app
