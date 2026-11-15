"""Instructor dashboard: class-wide summaries computed from the clickstream."""
from flask import Blueprint, render_template, request

from . import content
from .auth import instructor_required
from .db import get_db
from .tracking import MOODLE_COLUMNS, PAGE_SIZE, event_to_dict, filter_options, log_event, query_events

bp = Blueprint("analytics", __name__)


def _bars(rows):
    """Turn (label, value) rows into dicts with a width percentage for CSS bars."""
    rows = [(r[0], r[1]) for r in rows]
    top = max((v for _, v in rows), default=0) or 1
    return [{"label": label, "value": value, "width": round(100 * value / top, 1)} for label, value in rows]


@bp.get("/analytics")
@instructor_required
def dashboard():
    db = get_db()
    totals = db.execute(
        "SELECT COUNT(*) AS events, COUNT(DISTINCT user_id) AS active_users,"
        " COUNT(DISTINCT session_id) AS sessions,"
        " SUM(component = 'Video') AS video, SUM(component = 'Quiz') AS quiz,"
        " SUM(event_name LIKE '%clicked') AS clicks FROM events").fetchone()
    by_component = _bars(db.execute(
        "SELECT component, COUNT(*) FROM events GROUP BY component ORDER BY 2 DESC").fetchall())
    by_name = _bars(db.execute(
        "SELECT event_name, COUNT(*) FROM events GROUP BY event_name ORDER BY 2 DESC LIMIT 12").fetchall())
    by_day = _bars(db.execute(
        "SELECT substr(ts, 1, 10) AS day, COUNT(*) FROM events GROUP BY day ORDER BY day DESC LIMIT 14").fetchall()[::-1])
    by_lesson = _bars(db.execute(
        "SELECT event_context, COUNT(*) FROM events WHERE event_context LIKE 'Lesson:%' OR event_context LIKE 'Quiz:%'"
        " GROUP BY event_context ORDER BY 2 DESC LIMIT 9").fetchall())
    learners = db.execute(
        "SELECT u.id, u.username, u.full_name,"
        " (SELECT COUNT(*) FROM events e WHERE e.user_id = u.id) AS events,"
        " (SELECT MAX(ts) FROM events e WHERE e.user_id = u.id) AS last_active,"
        " (SELECT COUNT(*) FROM lesson_progress p WHERE p.user_id = u.id) AS lessons_done,"
        " (SELECT COUNT(*) FROM quiz_attempts q WHERE q.user_id = u.id AND q.submitted_at IS NOT NULL) AS attempts,"
        " (SELECT MAX(100 * q.score / q.max_score) FROM quiz_attempts q"
        "   WHERE q.user_id = u.id AND q.submitted_at IS NOT NULL) AS best_percent"
        " FROM users u WHERE u.role = 'learner' ORDER BY events DESC").fetchall()
    quizzes = db.execute(
        "SELECT lesson_id, COUNT(*) AS attempts, COUNT(DISTINCT user_id) AS learners,"
        " ROUND(AVG(100.0 * score / max_score)) AS avg_percent, MAX(100 * score / max_score) AS best_percent"
        " FROM quiz_attempts WHERE submitted_at IS NOT NULL GROUP BY lesson_id").fetchall()
    quiz_rows = [{**dict(q), "title": (content.find_lesson(q["lesson_id"])[1] or {}).get("title", q["lesson_id"])}
                 for q in quizzes]

    page = max(request.args.get("page", 1, type=int), 1)
    rows, total = query_events(None, PAGE_SIZE, (page - 1) * PAGE_SIZE)
    components, names = filter_options()
    log_event("Log report viewed", "Logs", "Analytics", "viewed the class analytics and log report",
              metadata={"page": page, "filters": dict(request.args)})
    return render_template(
        "analytics.html", totals=totals, by_component=by_component, by_name=by_name, by_day=by_day,
        by_lesson=by_lesson, learners=learners, quizzes=quiz_rows, total_lessons=content.total_lessons(),
        events=[event_to_dict(r) for r in rows], total=total, page=page,
        pages=max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1), components=components, names=names,
        columns=MOODLE_COLUMNS)
