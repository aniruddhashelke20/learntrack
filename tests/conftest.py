import re

import pytest

from learntrack import create_app
from learntrack.db import get_db


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(tmp_path / "test.sqlite")})


@pytest.fixture
def client(app):
    return app.test_client()


class Session:
    """Small helper that logs in and sends requests with the CSRF token."""

    def __init__(self, client):
        self.client = client
        self.token = None

    def _form_token(self, path):
        html = self.client.get(path).text
        return re.search(r'name="csrf_token" value="(\w+)"', html).group(1)

    def login(self, username="learner1", password="learn123"):
        response = self.client.post("/login", data={
            "username": username, "password": password, "csrf_token": self._form_token("/login")})
        if response.status_code == 302:
            html = self.client.get("/").text
            self.token = re.search(r'name="csrf-token" content="(\w+)"', html).group(1)
        return response

    def register(self, username, password="secret1", full_name="Test Learner", email="t@example.com"):
        response = self.client.post("/register", data={
            "username": username, "password": password, "full_name": full_name, "email": email,
            "csrf_token": self._form_token("/register")})
        if response.status_code == 302:
            html = self.client.get("/").text
            self.token = re.search(r'name="csrf-token" content="(\w+)"', html).group(1)
        return response

    def post_json(self, path, body=None):
        return self.client.post(path, json=body or {}, headers={"X-CSRF-Token": self.token})


@pytest.fixture
def session(client):
    return Session(client)


@pytest.fixture
def events(app):
    """Return a function that reads stored events as dicts."""
    def read(where="1=1", params=()):
        with app.app_context():
            rows = get_db().execute(f"SELECT * FROM events WHERE {where} ORDER BY id", params).fetchall()
            return [dict(r) for r in rows]
    return read
