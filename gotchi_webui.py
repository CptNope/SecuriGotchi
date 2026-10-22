"""Local authenticated dashboard. No browser-triggered command execution."""
import hmac
import os
from pathlib import Path
import secrets
import time
from functools import wraps
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from gotchi_auth import has_admin, verify_admin, signing_key
from gotchi_chain import validate_blocks, load_chain, verify_signature, CHAIN_FILE
from gotchi_memory import load_brain, changelog_path
from gotchi_threats import get_snapshot
from gotchi_monitor import overview

app = Flask(__name__)
app.config.update(
    SECRET_KEY=signing_key(),
    MAX_CONTENT_LENGTH=16 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    PERMANENT_SESSION_LIFETIME=900,
)
# Local HTTP only; enable secure cookies only behind a properly configured HTTPS endpoint.
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SECURIGOTCHI_HTTPS") == "1"
FAILED = {}
LOCK_SECONDS = 60


@app.before_request
def local_host_only():
    # Host-header allowlist protects localhost apps from DNS rebinding.
    host = request.host.split(":")[0].lower()
    if host not in ("localhost", "127.0.0.1", "[::1]"):
        return jsonify({"error": "Localhost only"}), 403


@app.after_request
def security_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


def require_admin(route):
    @wraps(route)
    def inner(*args, **kwargs):
        if not has_admin():
            return jsonify({"error": "Run python gotchi_auth.py init-admin first"}), 503
        if session.get("admin") != "admin":
            if request.path.startswith("/api/"):
                return jsonify({"error": "Login required"}), 401
            return redirect(url_for("login"))
        return route(*args, **kwargs)
    return inner


def csrf_valid(data):
    token = session.get("csrf")
    provided = data.get("csrf") if isinstance(data, dict) else None
    return isinstance(token, str) and isinstance(provided, str) and hmac.compare_digest(token, provided)


@app.route("/login", methods=["GET", "POST"])
def login():
    if not has_admin():
        return "Initialize a local admin with: python gotchi_auth.py init-admin", 503
    if request.method == "GET":
        if session.get("admin") == "admin":
            return redirect(url_for("index"))
        session["csrf"] = secrets.token_urlsafe(32)
        return render_template("login.html", error=None, csrf=session["csrf"])
    data = request.form
    if not csrf_valid(data):
        return "Invalid form token. Refresh the login page.", 400
    # In-process global attempt limit, sufficient to slow casual localhost guessing.
    now = time.monotonic()
    recent = [x for x in FAILED.get("admin", []) if now - x < LOCK_SECONDS]
    if len(recent) >= 5:
        FAILED["admin"] = recent
        return "Too many attempts; retry in one minute.", 429
    if not verify_admin(data.get("username", ""), data.get("password", "")):
        recent.append(now)
        FAILED["admin"] = recent
        session["csrf"] = secrets.token_urlsafe(32)
        return render_template("login.html", error="Invalid credentials", csrf=session["csrf"]), 401
    FAILED.pop("admin", None)
    session.clear()
    session.permanent = True
    session["admin"] = "admin"
    session["csrf"] = secrets.token_urlsafe(32)
    return redirect(url_for("index"))


@app.post("/logout")
@require_admin
def logout():
    if not csrf_valid(request.form):
        return "Invalid form token", 400
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@require_admin
def index():
    return render_template("index.html", csrf=session["csrf"])


@app.get("/api/brain")
@require_admin
def get_brain():
    brain = load_brain()
    return jsonify({"xp": brain.get("xp", 0), "level": brain.get("level", 1),
                    "mode": brain.get("mode", {}).get("name", "observer"),
                    "memory_count": len(brain.get("memory_log", []))})


@app.get("/api/memory")
@require_admin
def get_memory():
    path = Path(changelog_path)
    return jsonify(path.read_text(encoding="utf-8").splitlines()[-100:] if path.exists() else [])


@app.post("/api/query")
@require_admin
def query_memory():
    data = request.get_json(silent=True)
    if not csrf_valid({**data, "csrf": request.headers.get("X-CSRF-Token")}) if isinstance(data, dict) else True:
        return jsonify({"error": "Invalid form token"}), 403
    if not isinstance(data.get("query"), str) or not 1 <= len(data["query"].strip()) <= 500:
        return jsonify({"error": "Query must be 1-500 characters"}), 400
    try:
        from gotchi_query import get_results
        return jsonify([{"content": item} for item in get_results(data["query"].strip(), results_per_page=5)])
    except (ImportError, RuntimeError, OSError) as exc:
        app.logger.warning("Memory search unavailable: %s", exc)
        return jsonify({"error": "Semantic memory unavailable; install optional AI dependencies"}), 503


@app.post("/api/run_plugin")
@require_admin
def run_plugin():
    return jsonify({"error": "HTTP plugin execution remains disabled. Run trusted tools locally via plugin_runner.py."}), 403


@app.get("/api/chain_verify")
@require_admin
def verify_chain():
    try:
        blocks_valid = validate_blocks(load_chain())
        signed = verify_signature(CHAIN_FILE) if blocks_valid else False
        return jsonify({"valid": blocks_valid and signed, "blocks_valid": blocks_valid, "signed": signed})
    except (OSError, ValueError, TypeError, KeyError):
        return jsonify({"valid": False, "blocks_valid": False, "signed": False})


@app.get("/api/threats")
@require_admin
def threats():
    return jsonify(get_snapshot())


@app.get("/api/monitor")
@require_admin
def monitor_status():
    return jsonify(overview())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
