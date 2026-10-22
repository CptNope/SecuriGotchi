# Phase 9 — SecuriGotchi Setup Doctor

A safe installation and operational checklist for Windows, macOS, Linux,
WSL and Raspberry Pi OS. It **does not** install packages, register users,
start a collector, change permissions, expose ports or execute scans.

From the project directory after installing Python 3.11+:

```bash
python gotchi_doctor.py
python gotchi_doctor.py --json
python gotchi_doctor.py --strict
```

The default doctor reports:
- Python version and lightweight core dependencies.
- Whether the private application data directory exists and has safe
  ownership/Unix permissions (Windows ACL verification is explicitly limited).
- Whether the existing local admin and signing key are initialized.
- Whether an existing collector is active, stale, limited or not started,
  reading the database read-only without creating new files.
- Optional MCP SDK installation state.
- Whether more detailed probes were performed.

To opt in to additional bounded **read-only** probes:

```bash
python gotchi_doctor.py --probe-logs --probe-ollama
```

`--probe-logs` attempts to open a readable SSH authentication file,
or briefly queries the native OS event source via the supported adapter.
It never requests elevation. OS log availability does not prove all events are
being collected. `--probe-ollama` queries only the loopback Ollama model
list with a short timeout, reporting a model count without showing file paths.
No prompts or security-event telemetry are transmitted by this probe.

**Exit codes:** default mode exits 1 for definite failures and 0 if no
definite failures occur; warnings may remain. `--strict` also exits 1
for warnings, useful for a more conservative manual validation workflow.

The doctor is not a comprehensive security audit. To actually initialize
SecuriGotchi, use `python install.py`, then
`python gotchi_auth.py init-admin`, and start the dashboard and monitor
explicitly. Optional integrations should remain opt-in. For headless Raspberry
Pi, run the doctor from the Pi's terminal or an SSH session; remote dashboard
access is not enabled by the doctor.
