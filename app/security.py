"""Minimal CSRF protection: every POST must carry the token stored in the session."""
import hmac
import secrets

from flask import abort, current_app, request, session


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def protect_forms():
    if not current_app.config.get("CSRF_ENABLED", True):
        return
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf_token", "")
        if not expected or not hmac.compare_digest(sent.encode(), expected.encode()):
            abort(400, "Your session expired or the form was invalid. Please try again.")


def init_app(app):
    app.before_request(protect_forms)
    app.jinja_env.globals["csrf_token"] = csrf_token
