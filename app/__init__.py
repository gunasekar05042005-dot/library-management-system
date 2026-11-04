import os
from datetime import timedelta

from flask import Flask, render_template

from . import admin, auth, books, db, member, security


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.path.join(app.instance_path, "library.sqlite"),
        MIN_PASSWORD_LENGTH=8,
        CSRF_ENABLED=True,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_COOKIE_HTTPONLY=True,    # JavaScript cannot read the session cookie
        SESSION_COOKIE_SAMESITE="Lax",   # not sent on cross-site POSTs
        # SESSION_COOKIE_SECURE=True,    # enable when serving over HTTPS
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    security.init_app(app)
    app.cli.add_command(auth.create_admin_command)
    app.register_blueprint(auth.bp)
    app.register_blueprint(books.bp)
    app.register_blueprint(member.bp)
    app.register_blueprint(admin.bp)

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def error_page(e):
        titles = {400: "Request not accepted", 403: "Access denied", 404: "Page not found"}
        return render_template("error.html", code=e.code, title=titles[e.code],
                               message=e.description), e.code

    return app
