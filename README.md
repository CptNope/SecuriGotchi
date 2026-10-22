# SecuriGotchi — local cybersecurity companion

SecuriGotchi is a local-first gamified Python security companion for Ubuntu, WSL, and Raspberry Pi. It provides mission XP, a tamper-evident SHA-256 activity log, optional GPG signatures, optional ChromaDB semantic memory, local Ollama chat, CLI plugins, and a localhost dashboard.

> **Security notice:** Phase 2 adds **one local administrator account**, created only from the terminal, and protected dashboard sessions. There is no public sign-up, device enrollment, multi-user permissions, or secure remote access. Plugin execution remains disabled through HTTP. Do not expose the Flask dashboard to the public internet.

## Cross-platform core installer (Python 3.11+)

`python install.py` works on Windows, macOS, Linux and Raspberry Pi OS with suitable Python availability. On Windows, use `py -3.11 install.py` or newer. Run the created `.venv/Scripts/python.exe` on Windows and `.venv/bin/python` on Unix. The portable base includes Flask plus optional `psutil` system health; large AI packages are still optional (`python install.py --with-ai`). No elevated privileges are required. The portable dashboard binds to `127.0.0.1`; do not expose it to the internet.

**Coverage:** Windows/macOS can run local dashboard, persistent monitor health samples and local authentication, but **native Windows Event Log and macOS unified log ingestion are not implemented yet**. Linux and Raspberry Pi OS can additionally use text-based SSH log ingestion, systemd user services and opt-in notify-send notifications. Windows native users should not run the `.sh` installer; use `install.py`.

## Install (Python 3.11+)

```bash
git clone https://github.com/CptNope/SecuriGotchi.git
cd SecuriGotchi
bash secgotchi_install.sh
.venv/bin/python gotchi_auth.py init-admin
.venv/bin/python gotchi_webui.py
```

Open **http://127.0.0.1:5000** on the same computer and sign in as `admin` with your newly created password. First-run registration happens in the terminal and is closed after the administrator is created. The signing key and password verifier are stored by default in `~/.local/share/securigotchi/` (private directory, `0700`), not in the repository. For custom storage set `SECURIGOTCHI_DATA_DIR` to a user-owned, private directory before running setup or the dashboard.

**Important:** Keep a backup of this directory. No password reset UI or remote login is provided. The installer creates a Python virtual environment and installs the lightweight Flask core. It does not perform sudo changes or system-wide pip installs.

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

## Local SSH threat snapshot

The signed-in dashboard now displays counts of failed SSH logins, accepted logins, invalid-user events, and unique failing source IPs. The backend reads **only the last 1 MiB** of an accessible `/var/log/auth.log` or `/var/log/secure`. No sudo escalation or shell commands are used for log reading. The snapshot is sampled, not real-time detection or a complete intrusion history.

If neither default log is readable, set `SECURIGOTCHI_AUTH_LOG` to a local log file you are authorized to read. The dashboard shows an unavailable state rather than requiring elevated permissions. The browser receives summary counts, not raw log lines.

## Phase 3: Opt-in local monitoring

The continuous monitor is **not** started automatically by the web server. Run it in another terminal or supervised OS service:

```bash
.venv/bin/python gotchi_monitor.py once
.venv/bin/python gotchi_monitor.py watch --interval 60
.venv/bin/python gotchi_monitor.py status
```

The collector reads appended lines from a readable SSH authentication log and samples disk, memory and load. The **first poll starts at the current end of the log**, to avoid treating historical entries as fresh attacks. New log events and alert episodes are saved in a private SQLite database under `SECURIGOTCHI_DATA_DIR`. It keeps events for 7 days and alerts for 30 days. It never runs scans, reads private usernames into the database, or changes firewall rules.

Rules: five SSH failures from the same IP within five minutes trigger **high** severity (ten trigger **critical**); disk/memory thresholds of 80/90/97 percent trigger warning/high/critical respectively. Alert cooldown: 15 minutes per fingerprint, with immediate severity escalation.

The dashboard polls `/api/monitor` every 30 seconds and shows the Gotchi's derived **calm, watchful, alert, critical, or sleeping** mood. It does not award XP for attacks or pretend that monitoring is active when the collector is stale. The system is **not** a general IDS: no journald ingestion, email/push notifications, guaranteed delivery, or malware classification exists yet. Log rotations and large spikes can lose events; skipped bytes are reported, and the file-offset model may need deeper handling on unusual filesystems.

## Phase 4: Local desktop notifications and systemd user service

**Notifications are opt-in and local only.** On a Linux graphical session, install `notify-send` (Debian/Ubuntu: `sudo apt install libnotify-bin`) and test it:

```bash
.venv/bin/python gotchi_notifications.py test
.venv/bin/python gotchi_monitor.py watch --interval 60 --notify --notify-level high
```

The notifier only displays short alert titles and severity (not IP addresses, usernames, raw logs, or AI-generated commands). It requires a working desktop D-Bus session; **headless Raspberry Pi and most WSL sessions should run without `--notify`**. It processes new events only after explicit opt-in, retries when the desktop notification broker fails, and maintains a private SQLite cursor. Desktop broker acceptance does not guarantee the person saw the notification. A crash after delivery but before cursor persistence can repeat it.

To generate a **systemd user service** for the same checkout:

```bash
.venv/bin/python gotchi_service.py print
.venv/bin/python gotchi_service.py install
systemctl --user daemon-reload
systemctl --user enable --now securigotchi-monitor.service
systemctl --user status securigotchi-monitor.service
journalctl --user -u securigotchi-monitor.service -n 50
```

The generator writes a unit but **does not start or enable** it. Add `--notify` to the `gotchi_service.py install` command only for a logged-in graphical user session. Do not run a second manual `watch` concurrently; the collector uses a nonblocking Linux file lock. The service uses the default data directory `~/.local/share/securigotchi`; custom storage needs manual unit configuration. Avoid enabling systemd lingering to force user-session notifications on headless devices.

Service unit supervision does not guarantee log permissions, desktop D-Bus delivery, or cross-platform compatibility; test on the actual Ubuntu/WSL/Raspberry Pi system. Notifications do not depend on Ollama and never execute response actions.

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
2. Extend the local single-admin login with OS-independent auth support, secure reset/recovery, roles, hardware-device enrollment, stronger rate limiting, and a remote-access threat model.
3. Rewrite legacy plugins as permission-scoped, sandboxed, argument-validated and timeout-limited subprocesses.
4. Add dependency lockfiles, broader CI, tested Chroma migrations, signed manifest verification and Ollama integration tests.
5. Improve Raspberry Pi touchscreen interface, journald ingestion, severity/rule logic, device-local notification support and continuously collected metrics.

© Jeremy Anderson · [Jeremy Anderson Tech](https://jeremyanderson.tech)
