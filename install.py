"""Cross-platform SecuriGotchi core installer (Python 3.11+).

Run: python install.py
Optional heavy AI packages: python install.py --with-ai
No sudo, global pip installs, OS service changes, or auto-start actions.
"""
import argparse
from pathlib import Path
import os
import subprocess
import sys
import venv


def venv_python(root, windows=None):
    if windows is None:
        windows = os.name == "nt"
    return root / ".venv" / ("Scripts/python.exe" if windows else "bin/python")


def install(root, with_ai=False):
    root = Path(root).resolve()
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or later is required.")
    builder = venv.EnvBuilder(with_pip=True, clear=False)
    builder.create(root / ".venv")
    python = str(venv_python(root))
    requirements = ["requirements.txt"]
    if with_ai:
        requirements.append("requirements-ai.txt")
    for filename in requirements:
        subprocess.run(
            [python, "-m", "pip", "install", "-r", str(root / filename)],
            cwd=root, check=True,
        )
    return venv_python(root)


def main():
    parser = argparse.ArgumentParser(description="Install SecuriGotchi into a local virtual environment")
    parser.add_argument("--with-ai", action="store_true",
                        help="Install optional large sentence-transformer and Chroma dependencies")
    args = parser.parse_args()
    try:
        python = install(Path(__file__).resolve().parent, args.with_ai)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(status=1, message=f"Installation failed: {error}\n")
    print("SecuriGotchi core installed.")
    print(f"Initialize a local admin: {python} gotchi_auth.py init-admin")
    print(f"Launch the dashboard: {python} gotchi_webui.py")
    print("Visit http://127.0.0.1:5000 on the same device.")
    print("OS security-event ingestion may be unavailable on Windows/macOS.")


if __name__ == "__main__":
    main()
