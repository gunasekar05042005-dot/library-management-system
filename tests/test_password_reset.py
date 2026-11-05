"""Password reset: signed, expiring, single-use links; no account enumeration."""
import logging
import re
from urllib.parse import urlparse

from tests.conftest import login, uid_of
from tests.test_edge_cases import member_client

LINK_RE = re.compile(rb'href="(http[^"]*/reset-password/[^"]+)"')
MESSAGE = b"If that email is registered, a password reset link has been sent."


def request_link(client, email):
    resp = client.post("/forgot-password", data={"email": email})
    match = LINK_RE.search(resp.data)
    return resp, (urlparse(match.group(1).decode().replace("&amp;", "&")).path if match else None)


def test_known_email_gets_a_link_and_it_is_logged(app, client, caplog):
    member_client(app, "m@test.com")
    with caplog.at_level(logging.WARNING):
        resp, path = request_link(client, "m@test.com")
    assert MESSAGE in resp.data and path
    assert "reset-password" in caplog.text            # stands in for sending an email


def test_unknown_email_gets_the_same_message_and_no_link(client):
    resp, path = request_link(client, "nobody@test.com")
    assert MESSAGE in resp.data and path is None


def test_email_is_matched_case_insensitively(app, client):
    member_client(app, "m@test.com")
    assert request_link(client, "M@TEST.com")[1]


def test_reset_changes_the_password(app, client):
    member_client(app, "m@test.com")
    path = request_link(client, "m@test.com")[1]
    assert client.get(path).status_code == 200
    done = client.post(path, data={"password": "brandnew123", "confirm_password": "brandnew123"})
    assert done.status_code == 302 and done.headers["Location"].endswith("/login")
    fresh = app.test_client()
    assert b"Invalid email or password" in login(fresh, "m@test.com", "password123").data
    assert login(fresh, "m@test.com", "brandnew123").status_code == 302


def test_link_can_only_be_used_once(app, client):
    member_client(app, "m@test.com")
    path = request_link(client, "m@test.com")[1]
    client.post(path, data={"password": "brandnew123", "confirm_password": "brandnew123"})
    again = client.post(path, data={"password": "another12345", "confirm_password": "another12345"})
    assert again.status_code == 302 and "forgot-password" in again.headers["Location"]
    assert login(app.test_client(), "m@test.com", "brandnew123").status_code == 302   # second attempt had no effect


def test_expired_link_is_rejected(app, client):
    member_client(app, "m@test.com")
    path = request_link(client, "m@test.com")[1]
    app.config["RESET_TOKEN_MAX_AGE"] = -1
    assert "forgot-password" in client.get(path).headers["Location"]


def test_tampered_link_is_rejected(app, client):
    member_client(app, "m@test.com")
    path = request_link(client, "m@test.com")[1]
    assert "forgot-password" in client.get(path + "x").headers["Location"]
    assert "forgot-password" in client.get("/reset-password/not-a-token").headers["Location"]


def test_weak_or_mismatched_new_password_is_refused(app, client):
    member_client(app, "m@test.com")
    path = request_link(client, "m@test.com")[1]
    assert b"at least 8" in client.post(path, data={"password": "short", "confirm_password": "short"}).data
    assert b"do not match" in client.post(path, data={"password": "brandnew123", "confirm_password": "different1"}).data
    assert login(app.test_client(), "m@test.com", "password123").status_code == 302   # unchanged


def test_reset_signs_out_existing_sessions(app):
    stolen = member_client(app, "m@test.com")
    assert stolen.get("/books").status_code == 200
    owner = app.test_client()
    path = request_link(owner, "m@test.com")[1]
    owner.post(path, data={"password": "brandnew123", "confirm_password": "brandnew123"})
    resp = stolen.get("/books")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]
