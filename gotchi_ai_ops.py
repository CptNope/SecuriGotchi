"""Local AI Operations Center diagnostics and explicitly requested analysis.

No remote AI provider, scanning, privileged operation, or automatic inference.
The only provider contacted is Ollama on 127.0.0.1. All data sent to the local
model comes from the already-aggregated, allowlisted monitoring summary.
"""
import importlib.util
import json
import re
from urllib.error import URLError
from urllib.request import Request, ProxyHandler, build_opener

from gotchi_explain import explain
from gotchi_insights import snapshot
from gotchi_platform import describe_platform

TAGS_URL = "http://127.0.0.1:11434/api/tags"
MAX_TAGS_RESPONSE = 128 * 1024
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}$")


def valid_model_name(name):
    return isinstance(name, str) and MODEL_PATTERN.fullmatch(name) is not None


def parse_models(payload):
    """Accept only clean model names; model metadata is never passed to clients."""
    data = json.loads(payload)
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        raise ValueError("Invalid local Ollama model response")
    found = set()
    for item in data["models"][:500]:
        if isinstance(item, dict) and valid_model_name(item.get("name")):
            found.add(item["name"])
    return sorted(found, key=str.casefold)[:64]


def local_models(opener=None):
    client = opener if opener is not None else build_opener(ProxyHandler({}))
    request = Request(TAGS_URL, headers={"Accept": "application/json"})
    try:
        with client.open(request, timeout=3) as result:
            raw = result.read(MAX_TAGS_RESPONSE + 1)
        if len(raw) > MAX_TAGS_RESPONSE:
            raise RuntimeError("Ollama model list exceeded limit")
        return parse_models(raw)
    except (OSError, URLError, ValueError, TypeError) as exc:
        raise RuntimeError("Local Ollama is unavailable or returned invalid model data") from exc


def diagnostics():
    """Safe status, no filesystem locations or event details."""
    summary = snapshot()
    try:
        models = local_models()
        ollama_status = "ready"
    except RuntimeError:
        models, ollama_status = [], "unavailable"
    try:
        mcp_installed = importlib.util.find_spec("mcp") is not None
    except (ImportError, ValueError):
        mcp_installed = False
    platform = describe_platform()
    return {
        "platform": platform["os"],
        "raspberry_pi": platform["raspberry_pi"],
        "collector": summary["status"],
        "event_source": summary["source_status"],
        "mood": summary["mood"],
        "ollama": ollama_status,
        "models": models,
        "mcp_sdk": "installed" if mcp_installed else "not_installed",
        "mcp_server": "opt_in_only",
        "notice": "Health indicators are not proof a device is secure.",
    }


def analyze(model):
    from gotchi_settings import load
    if not load()['ai_enabled']:
        raise ValueError('Local AI is disabled in Settings')
    if not valid_model_name(model):
        raise ValueError("Select a valid local model")
    if snapshot()["status"] != "running":
        raise ValueError("The monitoring collector must be running first")
    # Only permit already installed local model identifiers, not arbitrary names
    # that could cause the Ollama daemon to resolve other model resources.
    if model not in local_models():
        raise ValueError("Selected model is not installed in the local Ollama instance")
    return explain(model=model)
