import json


def test_course_and_lesson_views_are_logged(session, client, events):
    session.login()
    assert client.get("/course/learning-analytics").status_code == 200
    page = client.get("/course/learning-analytics/lesson/clickstream-explained")
    assert page.status_code == 200 and "<video" in page.text
    logged = [(e["event_name"], e["component"], e["event_context"]) for e in events("event_name LIKE 'Course%'")]
    assert ("Course viewed", "System", "Course: Learning Analytics Foundations") in logged
    assert ("Course module viewed", "Text + Video", "Lesson: Clickstream data explained") in logged


def test_unknown_course_is_404(session, client):
    session.login()
    assert client.get("/course/nope").status_code == 404
    assert client.get("/course/learning-analytics/lesson/nope").status_code == 404


def test_quiz_answers_are_not_sent_to_the_browser(session, client):
    session.login()
    html = client.get("/course/learning-analytics/lesson/la-quiz").text
    assert "Measurement, collection, analysis, reporting" in html      # the option is shown
    assert "is the measurement, collection, analysis and reporting" not in html  # the explanation is not


def test_knowledge_check_feedback_and_logging(session, events):
    session.login()
    wrong = session.post_json("/api/lesson/what-is-la/check/la-check-1", {"choice": 0}).get_json()
    assert wrong == {"correct": False, "explanation": None}
    right = session.post_json("/api/lesson/what-is-la/check/la-check-1", {"choice": 1}).get_json()
    assert right["correct"] and "predictive" in right["explanation"]
    logged = events("event_name = 'Knowledge check answered'")
    assert [json.loads(e["metadata"])["correct"] for e in logged] == [False, True]
    assert session.post_json("/api/lesson/what-is-la/check/la-check-1", {"choice": 9}).status_code == 400


def test_marking_a_lesson_complete_updates_progress_once(session, client, events):
    session.login()
    assert session.post_json("/api/lesson/what-is-la/complete").get_json()["newly"] is True
    assert session.post_json("/api/lesson/what-is-la/complete").get_json()["newly"] is False
    assert len(events("event_name = 'Course activity completion updated'")) == 1
    assert "1 of 5 complete" in client.get("/").text


def test_quiz_attempt_is_graded_stored_and_logged(session, events):
    session.login()
    attempt_id = session.post_json("/api/quiz/la-quiz/start").get_json()["attempt_id"]
    answers = {"q1": 0, "q2": 1, "q3": 2, "q4": 1, "q5": 0}   # last one is wrong
    result = session.post_json("/api/quiz/la-quiz/submit", {"attempt_id": attempt_id, "answers": answers}).get_json()
    assert (result["score"], result["max_score"], result["percent"], result["passed"]) == (4, 5, 80, True)
    assert [r["correct"] for r in result["results"]] == [True, True, True, True, False]

    names = [e["event_name"] for e in events("component = 'Quiz' OR event_name LIKE 'Course activity%'")]
    assert names == ["Quiz attempt started", "Quiz attempt submitted", "Course activity completion updated"]
    submitted = events("event_name = 'Quiz attempt submitted'")[0]
    assert "scored 4/5 (80%)" in submitted["description"]
    assert json.loads(submitted["metadata"])["answers"] == answers

    # an attempt cannot be submitted twice
    again = session.post_json("/api/quiz/la-quiz/submit", {"attempt_id": attempt_id, "answers": answers})
    assert again.status_code == 400


def test_failed_quiz_does_not_complete_the_lesson(session, events):
    session.login()
    attempt_id = session.post_json("/api/quiz/web-quiz/start").get_json()["attempt_id"]
    result = session.post_json("/api/quiz/web-quiz/submit", {"attempt_id": attempt_id, "answers": {"q1": 0}}).get_json()
    assert result["passed"] is False and result["score"] == 0
    assert events("event_name LIKE 'Course activity%'") == []


def test_reviewing_an_attempt_is_logged_and_private(session, client, events):
    session.login()
    attempt_id = session.post_json("/api/quiz/web-quiz/start").get_json()["attempt_id"]
    session.post_json("/api/quiz/web-quiz/submit", {"attempt_id": attempt_id, "answers": {"q1": 1}})
    assert client.get(f"/api/quiz/attempt/{attempt_id}").get_json()["score"] == 1
    assert len(events("event_name = 'Quiz attempt reviewed'")) == 1

    client.post("/logout", data={"csrf_token": session.token})
    session.register("other")
    assert client.get(f"/api/quiz/attempt/{attempt_id}").status_code == 404
