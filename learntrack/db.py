"""SQLite access layer: connection handling, schema and demo accounts."""
import sqlite3
from datetime import datetime, timezone

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'learner' CHECK (role IN ('learner', 'instructor')),
    created_at    TEXT NOT NULL
);

-- One row per tracked action. The first seven columns after the keys mirror
-- the Moodle log format used as the reference clickstream example.
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,          -- when the action happened (UTC, ISO 8601)
    received_at   TEXT NOT NULL,          -- when the server stored it
    user_id       INTEGER REFERENCES users(id),
    session_id    TEXT,
    event_context TEXT NOT NULL,          -- e.g. "Lesson: Clickstream data explained"
    component     TEXT NOT NULL,          -- e.g. Video, Quiz, Text, System
    event_name    TEXT NOT NULL,          -- e.g. "Video paused"
    description   TEXT NOT NULL,          -- human-readable sentence
    origin        TEXT NOT NULL DEFAULT 'web',
    ip_address    TEXT,
    page_url      TEXT,
    metadata      TEXT NOT NULL DEFAULT '{}',  -- JSON with event-specific detail
    user_agent    TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events (user_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_name ON events (event_name);
CREATE INDEX IF NOT EXISTS idx_events_component ON events (component);

CREATE TABLE IF NOT EXISTS lesson_progress (
    user_id      INTEGER NOT NULL REFERENCES users(id),
    course_id    TEXT NOT NULL,
    lesson_id    TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    lesson_id    TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    submitted_at TEXT,
    score        INTEGER,
    max_score    INTEGER,
    answers      TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON quiz_attempts (user_id, lesson_id);
"""

DEMO_USERS = [
    ("learner1", "Asha Learner", "learner1@example.com", "learn123", "learner"),
    ("instructor", "Course Instructor", "instructor@example.com", "teach123", "instructor"),
]


def utcnow() -> str:
    """Current UTC time as an ISO 8601 string with millisecond precision."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Create tables if needed and make sure the demo accounts exist."""
    db = get_db()
    db.executescript(SCHEMA)
    for username, full_name, email, password, role in DEMO_USERS:
        exists = db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO users (username, full_name, email, password_hash, role, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (username, full_name, email, generate_password_hash(password), role, utcnow()),
            )
    db.commit()


@click.command("init-db")
def init_db_command() -> None:
    """Create the database tables and demo accounts."""
    init_db()
    click.echo("Database ready.")


@click.command("reset-db")
def reset_db_command() -> None:
    """Delete all data (users, clickstream, progress) and start fresh."""
    db = get_db()
    for table in ("events", "lesson_progress", "quiz_attempts", "users"):
        db.execute(f"DROP TABLE IF EXISTS {table}")
    db.commit()
    init_db()
    click.echo("Database reset.")


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(reset_db_command)
    with app.app_context():
        init_db()
