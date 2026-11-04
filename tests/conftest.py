import pytest

from app import create_app
from app.auth import create_user
from app.db import init_db


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite"),
                      "CSRF_ENABLED": False})
    with app.app_context():
        init_db()
        create_user("Admin User", "admin@test.com", "adminpass1", role="admin")
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, email="member@test.com", password="password123",
             name="Test Member", confirm=None, **extra):
    data = {"full_name": name, "email": email, "password": password,
            "confirm_password": password if confirm is None else confirm, **extra}
    return client.post("/register", data=data)


def login(client, email="member@test.com", password="password123", **extra):
    return client.post("/login", data={"email": email, "password": password, **extra})
