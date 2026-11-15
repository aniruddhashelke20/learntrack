def names(rows):
    return [r["event_name"] for r in rows]


def test_pages_require_login(client):
    assert client.get("/").status_code == 302
    assert "/login" in client.get("/activity").headers["Location"]
    assert client.get("/api/events").status_code == 403


def test_login_logs_event_and_opens_dashboard(session, client, events):
    assert session.login().status_code == 302
    assert "Asha Learner" in client.get("/").text
    assert "User logged in" in names(events())


def test_wrong_password_is_rejected_and_logged(session, events):
    response = session.login(password="wrong")
    assert response.status_code == 200
    assert "Incorrect username or password" in response.text
    assert names(events()) == ["User login failed"]


def test_register_creates_learner_with_hashed_password(session, app, events):
    assert session.register("newbie", password="secret1").status_code == 302
    from learntrack.db import get_db
    with app.app_context():
        user = get_db().execute("SELECT * FROM users WHERE username = 'newbie'").fetchone()
    assert user["role"] == "learner"
    assert "secret1" not in user["password_hash"]
    assert names(events())[:2] == ["User registered", "User logged in"]


def test_register_validates_input(session):
    assert "already taken" in session.register("learner1").text
    assert "at least 6 characters" in session.register("someone", password="123").text


def test_post_without_csrf_token_is_refused(client):
    assert client.post("/login", data={"username": "learner1", "password": "learn123"}).status_code == 400


def test_logout_ends_session(session, client, events):
    session.login()
    client.post("/logout", data={"csrf_token": session.token})
    assert client.get("/").status_code == 302
    assert names(events())[-1] == "User logged out"
