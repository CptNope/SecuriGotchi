# SecuriGotchi — local cybersecurity companion

SecuriGotchi is a local-first gamified Python security companion for Ubuntu, WSL, and Raspberry Pi. It provides mission XP, a tamper-evident SHA-256 activity log, optional GPG signatures, optional ChromaDB semantic memory, local Ollama chat, CLI plugins, and a localhost dashboard.

> **Security notice:** This project has no account registration, multi-user permissions, device enrollment, or secure remote access yet. The web dashboard is read-only for plugins and must not be exposed to the public internet.

## Install (Python 3.11+)

```bash
git clone https://github.com/CptNope/SecuriGotchi.git
cd SecuriGotchi
bash secgotchi_install.sh
.venv/bin/python gotchi_webui.py
```

Open **http://127.0.0.1:5000** on the same computer. The installer creates a Python virtual environment and installs the lightweight Flask core. It does not perform sudo changes or system-wide pip installs.

For optional semantic memory:

```bash
bash secgotchi_install.sh --with-ai
.venv/bin/python gotchi_memory.py "Completed authorized SSH audit" 25
.venv/bin/python gotchi_query.py "SSH audit" --page 1 --page-size 3
```

The first vector query may download an embedding model and can require substantial RAM. Ollama is a separate optional local service. Pull the model configured in `gotchi_ai_config.json`, start Ollama on loopback, then run:

```bash
.venv/bin/python gotchi_agent.py
```

## Local-only tools

```bash
.venv/bin/python gotchi_mission.py list
.venv/bin/python gotchi_mission.py run 2
.venv/bin/python plugin_runner.py
```

Only test systems and networks you own or have permission to inspect. Missions require explicit confirmation and no longer run through a shell. **Legacy plugins still need independent review**: many use shell commands and some are interactive. Do not run untrusted plugins or allow remote users to invoke them.

## Verify the activity ledger

```bash
.venv/bin/python gotchi_chain.py
```

Ledger blocks include the SHA-256 hash of their contents plus a previous-hash reference. Every block, including genesis, is checked. When GPG signing succeeds, the complete ledger is detached-signed. Without an available signing key the ledger is marked unsigned, even if its hashes are internally consistent. Hash chains are not immutable, decentralized blockchains. Runtime state is not encrypted at rest.

## Development

```bash
.venv/bin/python -m compileall -q gotchi_agent.py gotchi_chain.py gotchi_memory.py gotchi_mission.py gotchi_query.py gotchi_vector.py gotchi_webui.py plugin_manager.py plugin_runner.py plugins
.venv/bin/python -m unittest discover -s tests -v
```

GitHub Actions runs core syntax/tests on supported Python versions. Optional AI dependencies are not included in the core CI run.

## Further improvements

1. Move all runtime data to a dedicated directory; implement atomic multi-file transactions, locking, migration and backups.
2. Add local registration and login, CSRF tokens, roles, per-tool authorization and a remote access threat model.
3. Rewrite legacy plugins as permission-scoped, sandboxed, argument-validated and timeout-limited subprocesses.
4. Add dependency lockfiles, broader CI, tested Chroma migrations, signed manifest verification and Ollama integration tests.
5. Improve Raspberry Pi touchscreen interface and device-local notification support.

© Jeremy Anderson · [Jeremy Anderson Tech](https://jeremyanderson.tech)
