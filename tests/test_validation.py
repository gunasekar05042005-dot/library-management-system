"""Mandatory fields cannot be empty."""
import pytest

from app.db import get_db
from tests.conftest import register


@pytest.mark.parametrize("field,message", [
    ("name", b"Full name is required"),
    ("email", b"Email is required"),
    ("password", b"Password is required"),
])
def test_registration_rejects_each_empty_mandatory_field(client, app, field, message):
    resp = register(client, **{field: ""})
    assert resp.status_code == 200 and message in resp.data
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1   # only the admin


def test_registration_rejects_an_empty_confirmation(client):
    assert b"do not match" in register(client, confirm="").data
