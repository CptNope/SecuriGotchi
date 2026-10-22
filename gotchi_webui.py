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
from gotchi_insights import trends
from gotchi_ai_ops import diagnostics, analyze
from threading import BoundedSemaphore
from datetime import timedelta

_AI_LIMIT = BoundedSemaphore(1)

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
    from gotchi_settings import load
    app.permanent_session_lifetime = timedelta(minutes=load()['session_minutes'])


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
        from gotchi_auth import auth_epoch
        if session.get("admin") != "admin" or session.get('auth_epoch', 0) != auth_epoch():
            session.clear()
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
    from gotchi_auth import auth_epoch
    session['auth_epoch'] = auth_epoch()
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


@app.get('/settings')
@require_admin
def settings_page():
    return render_template('settings.html', csrf=session['csrf'])


@app.route('/api/settings', methods=['GET', 'POST'])
@require_admin
def settings_api():
    from gotchi_settings import FIELDS, load_document, save, ConflictError, runtime
    if request.method == 'POST':
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not csrf_valid({'csrf': request.headers.get('X-CSRF-Token')}):
            return jsonify(error='Invalid request token'), 403
        try:
            document = save(payload.get('values'), payload.get('revision'), payload.get('authorize_discovery') is True)
            return jsonify(**document, message='Settings saved. Collector changes apply on its next settings check, normally within five seconds plus any current poll. Reload the dashboard for display changes.')
        except ConflictError as error:
            return jsonify(error=str(error)), 409
        except (ValueError, OSError) as error:
            return jsonify(error=str(error)), 400
    from gotchi_platform import os_family
    from gotchi_auth import data_dir
    import shutil
    family = os_family()
    return jsonify(**load_document(), fields=FIELDS, field_order=list(FIELDS), collector=runtime(),
                   capabilities={'os': family, 'wifi': family == 'windows', 'notifications': family == 'linux' and bool(shutil.which('notify-send'))},
                   deployment={'data_directory': str(data_dir()),
                               'bind': '127.0.0.1:5000', 'ollama': '127.0.0.1:11434',
                               'auth_log_environment_override': bool(os.environ.get('SECURIGOTCHI_AUTH_LOG')),
                               'secure_cookies': app.config['SESSION_COOKIE_SECURE']})


@app.post('/api/settings/password')
@require_admin
def password_settings():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not csrf_valid({'csrf': request.headers.get('X-CSRF-Token')}):
        return jsonify(error='Invalid request token'), 403
    now = time.monotonic()
    attempts = [stamp for stamp in FAILED.get('password-change', []) if now - stamp < 60]
    if len(attempts) >= 5:
        return jsonify(error='Too many password attempts; retry in one minute'), 429
    attempts.append(now)
    FAILED['password-change'] = attempts
    if not isinstance(data.get('current'), str) or not isinstance(data.get('password'), str) or data.get('password') != data.get('confirm'):
        return jsonify(error='Enter current password and matching new passwords'), 400
    from gotchi_auth import change_password
    try:
        change_password(data['current'], data['password'])
    except ValueError as error:
        return jsonify(error=str(error)), 400
    FAILED.pop('password-change', None)
    session.clear()
    return jsonify(message='Password changed. All existing sessions are invalidated. Sign in with your new password.')


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


@app.get("/api/trends")
@require_admin
def security_trends():
    return jsonify(trends(24))


@app.get("/api/network")
@require_admin
def network_status():
    from gotchi_network import overview as network_overview
    return jsonify(network_overview())


@app.get("/api/ai/diagnostics")
@require_admin
def ai_diagnostics():
    return jsonify(diagnostics())


@app.post("/api/ai/explain")
@require_admin
def ai_explain():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not csrf_valid({
        "csrf": request.headers.get("X-CSRF-Token")
    }):
        return jsonify({"error": "Invalid request token"}), 403
    model = data.get("model")
    if not isinstance(model, str) or len(model) > 120:
        return jsonify({"error": "Select an installed local model"}), 400
    if not _AI_LIMIT.acquire(blocking=False):
        return jsonify({"error": "An AI analysis is already running"}), 429
    try:
        return jsonify(analyze(model))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        app.logger.warning("Local AI analysis unavailable")
        if str(exc).startswith("Local Ollama timed out after "):
            return jsonify({"error": str(exc)}), 503
        return jsonify({"error": "Local AI unavailable; check Ollama and collector"}), 503
    finally:
        _AI_LIMIT.release()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
