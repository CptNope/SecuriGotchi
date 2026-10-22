"""Local-only, read-only dashboard: never expose plugin execution to HTTP."""
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from gotchi_chain import validate_chain, validate_blocks, load_chain, verify_signature, CHAIN_FILE
from gotchi_memory import load_brain, changelog_path

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024


@app.after_request
def security_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' https://cdn.jsdelivr.net; "
        "script-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    return response


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/brain")
def get_brain():
    brain = load_brain()
    return jsonify({
        "xp": brain.get("xp", 0),
        "level": brain.get("level", 1),
        "mode": brain.get("mode", {}).get("name", "observer"),
        "memory_count": len(brain.get("memory_log", [])),
    })


@app.get("/api/memory")
def get_memory():
    path = Path(changelog_path)
    return jsonify(path.read_text(encoding="utf-8").splitlines()[-100:] if path.exists() else [])


@app.post("/api/query")
def query_memory():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("query"), str):
        return jsonify({"error": "A JSON query string is required"}), 400
    query = data["query"].strip()
    if not 1 <= len(query) <= 500:
        return jsonify({"error": "Query must be 1-500 characters"}), 400
    try:
        from gotchi_query import get_results
        return jsonify([{"content": text} for text in get_results(query, results_per_page=5)])
    except (ImportError, RuntimeError, OSError) as exc:
        app.logger.warning("Semantic memory unavailable: %s", exc)
        return jsonify({"error": "Semantic memory unavailable; install optional AI dependencies"}), 503


@app.post("/api/run_plugin")
def run_plugin():
    # Plugins include privileged shell commands and interactive prompts.
    # No authentication, authorization, or execution sandbox exists yet.
    return jsonify({
        "error": "Browser plugin execution is disabled until authentication and per-tool permissions are implemented. Run trusted plugins locally via plugin_runner.py."
    }), 403


@app.get("/api/chain_verify")
def verify_chain():
    try:
        blocks_valid = validate_blocks(load_chain())
        signed = verify_signature(CHAIN_FILE) if blocks_valid else False
        return jsonify({"valid": blocks_valid and signed, "blocks_valid": blocks_valid, "signed": signed})
    except (OSError, ValueError, TypeError, KeyError):
        return jsonify({"valid": False, "blocks_valid": False, "signed": False})


if __name__ == "__main__":
    app.run(host=os.environ.get("SECURIGOTCHI_HOST", "127.0.0.1"), port=5000, debug=False)
