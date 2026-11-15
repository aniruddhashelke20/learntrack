"""LearnTrack: a small learning app that records learner clickstream data."""
import os
import secrets
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, session

__version__ = "1.0.0"


def _load_secret_key(instance_path: str) -> str:
    """Use SECRET_KEY from the environment, or create one and keep it on disk."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    key_file = Path(instance_path) / "secret_key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
    return key_file.read_text().strip()


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        DATABASE=os.environ.get("LEARNTRACK_DB", os.path.join(app.instance_path, "learntrack.sqlite")),
        DISPLAY_TZ=os.environ.get("LEARNTRACK_TZ", "Asia/Kolkata"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=256 * 1024,  # clickstream batches are small
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _load_secret_key(app.instance_path)

    from . import analytics, auth, courses, db, tracking

    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(courses.bp)
    app.register_blueprint(tracking.bp)
    app.register_blueprint(analytics.bp)

    @app.before_request
    def csrf_protect():
        """Every state-changing request must carry the session's CSRF token."""
        if request.method in ("GET", "HEAD", "OPTIONS") or app.config.get("TESTING_NO_CSRF"):
            return
        sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        if sent is None and request.is_json:
            sent = (request.get_json(silent=True) or {}).get("csrf_token")
        if not sent or not secrets.compare_digest(sent, session.get("csrf_token", "")):
            abort(400, description="Missing or invalid CSRF token.")

    @app.context_processor
    def inject_globals():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return {"csrf_token": session["csrf_token"], "app_version": __version__}

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def handle_error(err):
        if request.path.startswith("/api/"):
            return jsonify(error=err.description), err.code
        return render_template("error.html", code=err.code, message=err.description), err.code

    return app
