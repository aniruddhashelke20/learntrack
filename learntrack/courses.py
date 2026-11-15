"""Learner-facing pages: dashboard, courses, lessons, knowledge checks and quizzes."""
import json

from flask import Blueprint, abort, g, jsonify, render_template, request

from . import content
from .auth import login_required
from .db import get_db, utcnow
from .tracking import log_event

bp = Blueprint("courses", __name__)


def completed_lessons(user_id) -> set:
    rows = get_db().execute("SELECT lesson_id FROM lesson_progress WHERE user_id = ?", (user_id,))
    return {r["lesson_id"] for r in rows}


def mark_complete(user_id, course_id, lesson_id) -> bool:
    """Record completion once; returns True if it was newly completed."""
    cur = get_db().execute(
        "INSERT OR IGNORE INTO lesson_progress (user_id, course_id, lesson_id, completed_at) VALUES (?, ?, ?, ?)",
        (user_id, course_id, lesson_id, utcnow()),
    )
    get_db().commit()
    return cur.rowcount == 1


@bp.get("/")
@login_required
def dashboard():
    done = completed_lessons(g.user["id"])
    courses = []
    for course in content.COURSES:
        finished = sum(l["id"] in done for l in course["lessons"])
        next_lesson = next((l for l in course["lessons"] if l["id"] not in done), course["lessons"][0])
        courses.append({**course, "finished": finished, "count": len(course["lessons"]),
                        "percent": round(100 * finished / len(course["lessons"])), "next": next_lesson,
                        "minutes": sum(l["minutes"] for l in course["lessons"])})
    recent = get_db().execute(
        "SELECT ts, event_name, event_context FROM events WHERE user_id = ? ORDER BY ts DESC, id DESC LIMIT 6",
        (g.user["id"],)).fetchall()
    log_event("Dashboard viewed", "System", "Dashboard", "viewed the dashboard")
    return render_template("dashboard.html", courses=courses, recent=recent,
                           done_count=len(done), total=content.total_lessons())


@bp.get("/course/<course_id>")
@login_required
def course(course_id):
    course = content.get_course(course_id)
    if course is None:
        abort(404, description="Course not found.")
    done = completed_lessons(g.user["id"])
    lessons = [{**l, "kind": content.lesson_kind(l), "done": l["id"] in done} for l in course["lessons"]]
    log_event("Course viewed", "System", f"Course: {course['title']}", f"viewed course '{course_id}'",
              metadata={"course_id": course_id})
    return render_template("course.html", course=course, lessons=lessons,
                           finished=sum(l["done"] for l in lessons))


@bp.get("/course/<course_id>/lesson/<lesson_id>")
@login_required
def lesson(course_id, lesson_id):
    course, lesson = content.get_lesson(course_id, lesson_id)
    if lesson is None:
        abort(404, description="Lesson not found.")
    index = course["lessons"].index(lesson)
    kind = content.lesson_kind(lesson)
    attempts = []
    if kind == "Quiz":
        attempts = get_db().execute(
            "SELECT id, submitted_at, score, max_score FROM quiz_attempts"
            " WHERE user_id = ? AND lesson_id = ? AND submitted_at IS NOT NULL ORDER BY id DESC",
            (g.user["id"], lesson_id)).fetchall()
    log_event("Course module viewed", kind, f"{'Quiz' if kind == 'Quiz' else 'Lesson'}: {lesson['title']}",
              f"viewed the {kind.lower()} lesson '{lesson_id}' in course '{course_id}'",
              metadata={"course_id": course_id, "lesson_id": lesson_id, "lesson_type": kind})
    return render_template(
        "lesson.html", course=course, lesson=lesson, kind=kind, attempts=attempts,
        done=lesson_id in completed_lessons(g.user["id"]), position=index + 1,
        prev_lesson=course["lessons"][index - 1] if index else None,
        next_lesson=course["lessons"][index + 1] if index + 1 < len(course["lessons"]) else None)


@bp.post("/api/lesson/<lesson_id>/complete")
@login_required
def complete_lesson(lesson_id):
    course, lesson = content.find_lesson(lesson_id)
    if lesson is None:
        abort(404, description="Lesson not found.")
    newly = mark_complete(g.user["id"], course["id"], lesson_id)
    if newly:
        log_event("Course activity completion updated", "System", f"Lesson: {lesson['title']}",
                  f"marked lesson '{lesson_id}' as complete",
                  metadata={"course_id": course["id"], "lesson_id": lesson_id, "state": "complete"})
    return jsonify(completed=True, newly=newly)


@bp.post("/api/lesson/<lesson_id>/check/<check_id>")
@login_required
def answer_check(lesson_id, check_id):
    """Grade one inline knowledge-check question and log the answer."""
    _course, lesson = content.find_lesson(lesson_id)
    block = content.get_block(lesson, "check", check_id) if lesson else None
    if block is None:
        abort(404, description="Question not found.")
    choice = (request.get_json(silent=True) or {}).get("choice")
    if not isinstance(choice, int) or not 0 <= choice < len(block["options"]):
        abort(400, description="'choice' must be the index of an option.")
    correct = choice == block["answer"]
    log_event("Knowledge check answered", "Text", f"Lesson: {lesson['title']}",
              f"answered knowledge check '{check_id}' {'correctly' if correct else 'incorrectly'}"
              f" with option {choice + 1} ('{block['options'][choice]}')",
              metadata={"check_id": check_id, "choice": choice, "correct": correct})
    # The explanation (and so the answer) is only revealed once the learner gets it right.
    return jsonify(correct=correct, explanation=block["explanation"] if correct else None)


# ------------------------------------------------------------------ quiz ----

def _quiz_or_404(lesson_id):
    course, lesson = content.find_lesson(lesson_id)
    quiz = content.get_block(lesson, "quiz") if lesson else None
    if quiz is None:
        abort(404, description="Quiz not found.")
    return course, lesson, quiz


@bp.post("/api/quiz/<lesson_id>/start")
@login_required
def start_quiz(lesson_id):
    _course, lesson, quiz = _quiz_or_404(lesson_id)
    db = get_db()
    cur = db.execute("INSERT INTO quiz_attempts (user_id, lesson_id, started_at) VALUES (?, ?, ?)",
                     (g.user["id"], lesson_id, utcnow()))
    db.commit()
    log_event("Quiz attempt started", "Quiz", f"Quiz: {lesson['title']}",
              f"started attempt {cur.lastrowid} of quiz '{lesson_id}'",
              metadata={"attempt_id": cur.lastrowid, "questions": len(quiz["questions"])})
    return jsonify(attempt_id=cur.lastrowid), 201


@bp.post("/api/quiz/<lesson_id>/submit")
@login_required
def submit_quiz(lesson_id):
    course, lesson, quiz = _quiz_or_404(lesson_id)
    data = request.get_json(silent=True) or {}
    answers = data.get("answers") if isinstance(data.get("answers"), dict) else {}
    db = get_db()
    attempt = db.execute(
        "SELECT * FROM quiz_attempts WHERE id = ? AND user_id = ? AND lesson_id = ?",
        (data.get("attempt_id"), g.user["id"], lesson_id)).fetchone()
    if attempt is None:
        abort(404, description="Attempt not found. Start the quiz first.")
    if attempt["submitted_at"]:
        abort(400, description="This attempt was already submitted.")

    results, score = [], 0
    for q in quiz["questions"]:
        chosen = answers.get(q["id"])
        correct = chosen == q["answer"]
        score += correct
        results.append({"id": q["id"], "chosen": chosen, "answer": q["answer"],
                        "correct": correct, "explanation": q["explanation"]})
    max_score = len(quiz["questions"])
    percent = round(100 * score / max_score)
    passed = percent >= quiz["pass_mark"]
    db.execute("UPDATE quiz_attempts SET submitted_at = ?, score = ?, max_score = ?, answers = ? WHERE id = ?",
               (utcnow(), score, max_score, json.dumps(answers), attempt["id"]))
    db.commit()
    log_event("Quiz attempt submitted", "Quiz", f"Quiz: {lesson['title']}",
              f"submitted attempt {attempt['id']} of quiz '{lesson_id}' and scored {score}/{max_score} ({percent}%)",
              metadata={"attempt_id": attempt["id"], "score": score, "max_score": max_score,
                        "percent": percent, "passed": passed, "answers": answers})
    if passed and mark_complete(g.user["id"], course["id"], lesson_id):
        log_event("Course activity completion updated", "System", f"Quiz: {lesson['title']}",
                  f"completed lesson '{lesson_id}' by passing the quiz",
                  metadata={"course_id": course["id"], "lesson_id": lesson_id, "state": "complete"})
    return jsonify(score=score, max_score=max_score, percent=percent, passed=passed,
                   pass_mark=quiz["pass_mark"], results=results)


@bp.get("/api/quiz/attempt/<int:attempt_id>")
@login_required
def review_attempt(attempt_id):
    attempt = get_db().execute(
        "SELECT * FROM quiz_attempts WHERE id = ? AND user_id = ? AND submitted_at IS NOT NULL",
        (attempt_id, g.user["id"])).fetchone()
    if attempt is None:
        abort(404, description="Attempt not found.")
    _course, lesson, quiz = _quiz_or_404(attempt["lesson_id"])
    answers = json.loads(attempt["answers"])
    results = [{"id": q["id"], "chosen": answers.get(q["id"]), "answer": q["answer"],
                "correct": answers.get(q["id"]) == q["answer"], "explanation": q["explanation"]}
               for q in quiz["questions"]]
    log_event("Quiz attempt reviewed", "Quiz", f"Quiz: {lesson['title']}",
              f"reviewed attempt {attempt_id} of quiz '{attempt['lesson_id']}'",
              metadata={"attempt_id": attempt_id})
    return jsonify(score=attempt["score"], max_score=attempt["max_score"],
                   percent=round(100 * attempt["score"] / attempt["max_score"]), results=results)
