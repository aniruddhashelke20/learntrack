"""Clickstream collection, storage and retrieval.

Two sources feed the ``events`` table:

* the server itself (``log_event``) for things it knows for certain:
  logins, page views, quiz grading, exports;
* the browser tracker (``static/js/tracker.js``), which posts batches of
  interaction events (clicks, scrolling, video actions...) to ``POST /api/events``.
"""
import csv
import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, Response, abort, current_app, g, jsonify, render_template, request, session

from .auth import login_required
from .db import get_db, utcnow

bp = Blueprint("tracking", __name__)

MAX_BATCH = 100
MAX_TEXT = 500
PAGE_SIZE = 25
MOODLE_COLUMNS = ["Time", "Event context", "Component", "Event name", "Description", "Origin", "IP address"]


# ---------------------------------------------------------------- writing ----

def client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() or request.remote_addr or ""


def current_session_id() -> str:
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    return session["sid"]


def _clean(value, limit=MAX_TEXT) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def _event_time(client_ts) -> str:
    """Trust the browser's timestamp only if it is close to the server clock."""
    now = datetime.now(timezone.utc)
    try:
        ts = datetime.fromisoformat(str(client_ts).replace("Z", "+00:00"))
        if ts.tzinfo and abs(now - ts) <= timedelta(minutes=10):
            return ts.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    except (TypeError, ValueError):
        pass
    return utcnow()


def log_event(event_name, component, context, action, *, metadata=None, user_id=None,
              page_url=None, client_ts=None, commit=True) -> None:
    """Store one clickstream event.

    ``action`` is the sentence fragment after the subject, e.g.
    ``"paused video 'HTTP in 60 seconds' at 0:21"``; the stored description
    becomes ``"User 7 paused video ..."`` like the Moodle reference logs.
    """
    if user_id is None and g.get("user") is not None:
        user_id = g.user["id"]
    subject = f"User {user_id}" if user_id else "A visitor"
    get_db().execute(
        "INSERT INTO events (ts, received_at, user_id, session_id, event_context, component,"
        " event_name, description, origin, ip_address, page_url, metadata, user_agent)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'web', ?, ?, ?, ?)",
        (
            _event_time(client_ts) if client_ts else utcnow(),
            utcnow(),
            user_id,
            current_session_id(),
            _clean(context, 200) or "LearnTrack",
            _clean(component, 60) or "System",
            _clean(event_name, 80),
            f"{subject} {_clean(action)}",
            client_ip(),
            _clean(page_url or request.path, 300),
            json.dumps(metadata or {}, ensure_ascii=False)[:4000],
            _clean(request.headers.get("User-Agent"), 300),
        ),
    )
    if commit:
        get_db().commit()


@bp.post("/api/events")
@login_required
def collect_events():
    """Receive a batch of browser events: ``{"events": [{...}, ...]}``."""
    payload = request.get_json(silent=True) or {}
    events = payload.get("events")
    if not isinstance(events, list) or not events:
        abort(400, description="Body must be JSON with a non-empty 'events' list.")
    stored = 0
    for item in events[:MAX_BATCH]:
        if not isinstance(item, dict) or not item.get("event_name"):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        log_event(
            item["event_name"],
            item.get("component") or "System",
            item.get("context") or "LearnTrack",
            item.get("action") or "performed an action",
            metadata=metadata,
            page_url=item.get("page_url"),
            client_ts=item.get("ts"),
            commit=False,
        )
        stored += 1
    get_db().commit()
    return jsonify(stored=stored), 201


# ---------------------------------------------------------------- reading ----

def _filters(for_user_id=None):
    """Build a WHERE clause from the query string (shared by page, API and export)."""
    clauses, params = [], []
    if for_user_id is not None:
        clauses.append("e.user_id = ?")
        params.append(for_user_id)
    elif request.args.get("user_id"):
        clauses.append("e.user_id = ?")
        params.append(request.args["user_id"])
    for column in ("component", "event_name"):
        if request.args.get(column):
            clauses.append(f"e.{column} = ?")
            params.append(request.args[column])
    if request.args.get("q"):
        clauses.append("(e.description LIKE ? OR e.event_context LIKE ?)")
        params += [f"%{request.args['q']}%"] * 2
    if request.args.get("from"):
        clauses.append("e.ts >= ?")
        params.append(request.args["from"])
    if request.args.get("to"):
        clauses.append("e.ts <= ?")
        params.append(request.args["to"] + "T23:59:59.999Z" if len(request.args["to"]) == 10 else request.args["to"])
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def query_events(for_user_id=None, limit=PAGE_SIZE, offset=0):
    where, params = _filters(for_user_id)
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM events e{where}", params).fetchone()[0]
    sql = (
        "SELECT e.*, u.username, u.full_name FROM events e LEFT JOIN users u ON u.id = e.user_id"
        f"{where} ORDER BY e.ts DESC, e.id DESC"
    )
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params = params + [limit, offset]
    return db.execute(sql, params).fetchall(), total


def event_to_dict(row) -> dict:
    data = {key: row[key] for key in (
        "id", "ts", "received_at", "user_id", "username", "session_id", "event_context", "component",
        "event_name", "description", "origin", "ip_address", "page_url", "user_agent")}
    data["metadata"] = json.loads(row["metadata"] or "{}")
    return data


def _scope_user_id():
    """Learners may only read their own clickstream; instructors can read all."""
    scope = request.args.get("scope", "mine")
    if scope == "all":
        if g.user["role"] != "instructor":
            abort(403, description="Only instructors can read other learners' data.")
        return None
    return g.user["id"]


def _local_time(iso_ts: str) -> str:
    """Format like the reference export: ``5/08/24, 02:57:25``."""
    try:
        tz = ZoneInfo(current_app.config["DISPLAY_TZ"])
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    local = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(tz)
    return f"{local.day}/{local:%m/%y, %H:%M:%S}"


@bp.get("/api/events")
@login_required
def list_events():
    """JSON retrieval with filters and paging."""
    limit = min(max(request.args.get("limit", PAGE_SIZE, type=int), 1), 1000)
    offset = max(request.args.get("offset", 0, type=int), 0)
    rows, total = query_events(_scope_user_id(), limit, offset)
    return jsonify(total=total, limit=limit, offset=offset, events=[event_to_dict(r) for r in rows])


@bp.get("/api/events/export")
@login_required
def export_events():
    """Download the clickstream as CSV (Moodle-style or full) or JSON."""
    fmt = request.args.get("format", "csv")
    scope_user = _scope_user_id()
    rows, total = query_events(scope_user, limit=None)
    log_event("Clickstream exported", "Activity log", "Activity log",
              f"exported {total} clickstream events as {fmt}",
              metadata={"format": fmt, "rows": total, "scope": "mine" if scope_user else "all"})
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    if fmt == "json":
        body = json.dumps([event_to_dict(r) for r in rows], indent=2, ensure_ascii=False)
        return Response(body, mimetype="application/json", headers={
            "Content-Disposition": f"attachment; filename=clickstream-{stamp}.json"})

    out = io.StringIO()
    writer = csv.writer(out)
    if fmt == "full":
        writer.writerow(MOODLE_COLUMNS + ["User id", "Username", "Session id", "Page URL", "Timestamp (UTC)", "Metadata"])
    else:
        writer.writerow(MOODLE_COLUMNS)
    for r in rows:
        line = [_local_time(r["ts"]), r["event_context"], r["component"], r["event_name"],
                r["description"], r["origin"], r["ip_address"]]
        if fmt == "full":
            line += [r["user_id"], r["username"], r["session_id"], r["page_url"], r["ts"], r["metadata"]]
        writer.writerow(line)
    return Response(out.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": f"attachment; filename=clickstream-{stamp}.csv"})


def filter_options(for_user_id=None):
    db = get_db()
    where, params = (" WHERE user_id = ?", [for_user_id]) if for_user_id else ("", [])
    components = [r[0] for r in db.execute(f"SELECT DISTINCT component FROM events{where} ORDER BY 1", params)]
    names = [r[0] for r in db.execute(f"SELECT DISTINCT event_name FROM events{where} ORDER BY 1", params)]
    return components, names


@bp.get("/activity")
@login_required
def activity():
    """A learner's own clickstream, searchable and exportable."""
    page = max(request.args.get("page", 1, type=int), 1)
    uid = g.user["id"]
    rows, total = query_events(uid, PAGE_SIZE, (page - 1) * PAGE_SIZE)
    db = get_db()
    summary = db.execute(
        "SELECT COUNT(*) AS total,"
        " SUM(event_name LIKE '%viewed') AS views,"
        " SUM(event_name LIKE '%clicked') AS clicks,"
        " SUM(component = 'Video') AS video,"
        " SUM(component = 'Quiz') AS quiz,"
        " COUNT(DISTINCT session_id) AS sessions"
        " FROM events WHERE user_id = ?", (uid,)).fetchone()
    components, names = filter_options(uid)
    log_event("Activity log viewed", "Activity log", "Activity log",
              f"viewed their activity log (page {page})", metadata={"page": page, "filters": dict(request.args)})
    return render_template(
        "activity.html", events=[event_to_dict(r) for r in rows], total=total, page=page,
        pages=max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1), summary=summary,
        components=components, names=names, columns=MOODLE_COLUMNS)
