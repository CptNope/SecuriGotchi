#!/usr/bin/env bash
set -euo pipefail
echo "SecuriGotchi local installer (Ubuntu/WSL/Raspberry Pi)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
if ! command -v python3 >/dev/null || ! python3 -c 'import sys; sys.exit(sys.version_info < (3,11))'; then
  echo "Install Python 3.11+ and python3-venv first." >&2
  exit 1
fi
python3 -m venv .venv || {
  echo "venv failed. On Debian/Ubuntu install python3-venv." >&2
  exit 1
}
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
if [ "$#" -gt 0 ] && [ "$1" = "--with-ai" ]; then
  .venv/bin/python -m pip install -r requirements-ai.txt
fi
echo "Installed. Start the localhost dashboard:"
echo "  .venv/bin/python gotchi_webui.py"
echo "Open http://127.0.0.1:5000 on this machine."
echo "GPG and local diagnostic tools are optional OS-level installations."
