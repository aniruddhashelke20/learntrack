"""Registration, login and logout for learners (and the instructor account)."""
import functools
import re
import secrets
import uuid

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, utcnow

bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone() if user_id else None


def login_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            if request.path.startswith("/api/"):
                abort(403, description="Please log in.")
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)
    return wrapped


def instructor_required(view):
    @functools.wraps(view)
    @login_required
    def wrapped(**kwargs):
        if g.user["role"] != "instructor":
            abort(403, description="This page is for instructors only.")
        return view(**kwargs)
    return wrapped


def _start_session(user) -> None:
    session.clear()
    session["user_id"] = user["id"]
    session["sid"] = uuid.uuid4().hex          # groups one visit's clickstream
    session["csrf_token"] = secrets.token_hex(16)
    g.user = user


def _safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else url_for("courses.dashboard")


@bp.route("/register", methods=("GET", "POST"))
def register():
    from .tracking import log_event

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        error = None
        if not USERNAME_RE.match(username):
            error = "Username must be 3-30 letters, digits, dots, dashes or underscores."
        elif not full_name:
            error = "Please enter your name."
        elif "@" not in email:
            error = "Please enter a valid email address."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            error = f"The username '{username}' is already taken."

        if error is None:
            cur = db.execute(
                "INSERT INTO users (username, full_name, email, password_hash, role, created_at)"
                " VALUES (?, ?, ?, ?, 'learner', ?)",
                (username, full_name, email, generate_password_hash(password), utcnow()),
            )
            db.commit()
            user = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
            _start_session(user)
            log_event("User registered", "Auth", "LearnTrack", f"created the learner account '{username}'")
            log_event("User logged in", "Auth", "LearnTrack", "logged in after registering",
                      metadata={"method": "registration"})
            return redirect(url_for("courses.dashboard"))
        flash(error, "error")
    return render_template("register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    from .tracking import log_event

    if g.user is not None and request.method == "GET":
        return redirect(url_for("courses.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            log_event("User login failed", "Auth", "LearnTrack",
                      f"failed to log in with username '{username[:30]}'",
                      user_id=user["id"] if user else None)
            flash("Incorrect username or password.", "error")
        else:
            _start_session(user)
            log_event("User logged in", "Auth", "LearnTrack", "logged in", metadata={"method": "password"})
            return redirect(_safe_next(request.args.get("next")))
    return render_template("login.html")


@bp.post("/logout")
def logout():
    from .tracking import log_event

    if g.user is not None:
        log_event("User logged out", "Auth", "LearnTrack", "logged out")
    session.clear()
    return redirect(url_for("auth.login"))
