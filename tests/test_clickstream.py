import csv
import io
import json

MOODLE_COLUMNS = ["Time", "Event context", "Component", "Event name", "Description", "Origin", "IP address"]


def video_event(**overrides):
    event = {
        "event_name": "Video paused", "component": "Video", "context": "Lesson: Clickstream data explained",
        "action": "paused video 'Clickstream in one minute' at 0:21",
        "metadata": {"video_id": "clickstream-explained", "position": 21.4},
        "page_url": "/course/learning-analytics/lesson/clickstream-explained",
    }
    event.update(overrides)
    return event


def test_browser_events_are_stored_with_user_session_and_ip(session, events):
    session.login()
    response = session.post_json("/api/events", {"events": [
        video_event(),
        video_event(event_name="Link clicked", component="Text", action="clicked link 'Next'", metadata={"x": 10, "y": 20}),
    ]})
    assert response.status_code == 201 and response.get_json() == {"stored": 2}

    stored = events("event_name = 'Video paused'")[0]
    assert stored["user_id"] == 1
    assert stored["description"] == "User 1 paused video 'Clickstream in one minute' at 0:21"
    assert stored["event_context"] == "Lesson: Clickstream data explained"
    assert stored["origin"] == "web" and stored["ip_address"] == "127.0.0.1"
    assert stored["session_id"] and stored["ts"].endswith("Z")
    assert json.loads(stored["metadata"])["position"] == 21.4


def test_collect_rejects_anonymous_missing_csrf_and_bad_bodies(client, session):
    assert client.post("/api/events", json={"events": [video_event()]}).status_code in (400, 403)
    session.login()
    assert client.post("/api/events", json={"events": [video_event()]}).status_code == 400   # no CSRF token
    assert session.post_json("/api/events", {"events": []}).status_code == 400
    assert session.post_json("/api/events", {"events": [{"no": "name"}]}).get_json() == {"stored": 0}


def test_csrf_token_in_body_is_accepted_for_beacons(session, client):
    """navigator.sendBeacon cannot set headers, so the token may travel in the JSON body."""
    session.login()
    response = client.post("/api/events", json={"events": [video_event()], "csrf_token": session.token})
    assert response.status_code == 201


def test_events_api_filters_and_pages(session, client):
    session.login()
    session.post_json("/api/events", {"events": [video_event() for _ in range(5)]})
    data = client.get("/api/events?component=Video&limit=2").get_json()
    assert data["total"] == 5 and len(data["events"]) == 2
    assert all(e["component"] == "Video" for e in data["events"])
    assert client.get("/api/events?event_name=Video+played").get_json()["total"] == 0
    assert client.get("/api/events?q=0:21").get_json()["total"] == 5


def test_learners_only_see_their_own_events(session, client):
    session.login()
    session.post_json("/api/events", {"events": [video_event()]})
    client.post("/logout", data={"csrf_token": session.token})

    session.register("second")
    mine = client.get("/api/events").get_json()
    assert mine["total"] > 0 and {e["username"] for e in mine["events"]} == {"second"}
    assert client.get("/api/events?scope=all").status_code == 403
    assert client.get("/api/events/export?scope=all").status_code == 403
    assert client.get("/analytics").status_code == 403


def test_instructor_sees_everyone(session, client):
    session.login()
    session.post_json("/api/events", {"events": [video_event()]})
    client.post("/logout", data={"csrf_token": session.token})

    session.login("instructor", "teach123")
    everyone = client.get("/api/events?scope=all&limit=100").get_json()
    assert {"learner1", "instructor"} <= {e["username"] for e in everyone["events"]}
    page = client.get("/analytics")
    assert page.status_code == 200 and "Events by component" in page.text and "Asha Learner" in page.text
    only_learner = client.get("/api/events?scope=all&user_id=1").get_json()
    assert {e["username"] for e in only_learner["events"]} == {"learner1"}


def test_csv_export_matches_the_moodle_log_format(session, client, events):
    session.login()
    session.post_json("/api/events", {"events": [video_event()]})
    response = client.get("/api/events/export?format=csv")
    assert response.mimetype == "text/csv" and "attachment" in response.headers["Content-Disposition"]
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == MOODLE_COLUMNS
    paused = next(r for r in rows if r[3] == "Video paused")
    assert paused[1:] == ["Lesson: Clickstream data explained", "Video", "Video paused",
                          "User 1 paused video 'Clickstream in one minute' at 0:21", "web", "127.0.0.1"]
    assert events("event_name = 'Clickstream exported'")   # exporting is itself tracked


def test_full_csv_and_json_exports(session, client):
    session.login()
    session.post_json("/api/events", {"events": [video_event()]})
    full = list(csv.reader(io.StringIO(client.get("/api/events/export?format=full").text)))
    assert full[0][:7] == MOODLE_COLUMNS and "Metadata" in full[0] and "Session id" in full[0]
    exported = json.loads(client.get("/api/events/export?format=json&component=Video").text)
    assert len(exported) == 1 and exported[0]["metadata"]["video_id"] == "clickstream-explained"


def test_activity_page_lists_events(session, client):
    session.login()
    session.post_json("/api/events", {"events": [video_event()]})
    html = client.get("/activity?component=Video").text
    assert "Video paused" in html and "matching events" in html
