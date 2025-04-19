# SecuriGotchi

![version](https://img.shields.io/badge/version-1.4-blue) ![build](https://img.shields.io/badge/build-passing-brightgreen) ![platform](https://img.shields.io/badge/platform-RaspberryPi4–Kali-black) ![license](https://img.shields.io/github/license/CptNope/SecuriGotchi) ![autonomy](https://img.shields.io/badge/mode-dynamic-yellow)

SecuriGotchi is a **cyberpunk-inspired, terminal-based AI companion** built for cybersecurity operations, training, and monitoring on a Raspberry Pi 4B with a 3.5” touchscreen. It combines **ANSI art**, **gamified missions**, **persistent memory**, **AI assistance**, and **real-world tools** into a single package.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Requirements](#requirements)
5. [Installation](#installation)
6. [Quick Start](#quick-start)
7. [Core Commands](#core-commands)
8. [Configuration Files](#configuration-files)
9. [Missions & XP System](#missions--xp-system)
10. [Plugin System](#plugin-system)
11. [Autonomy Modes](#autonomy-modes)
12. [Memory & AI Assistant](#memory--ai-assistant)
13. [Threat Monitoring](#threat-monitoring)
14. [Diagnostics Panel](#diagnostics-panel)
15. [Boot-to-Terminal](#boot-to-terminal)
16. [Contributing](#contributing)
17. [Troubleshooting](#troubleshooting)
18. [License](#license)

---

## Introduction

SecuriGotchi brings the nostalgia of terminal pets into modern cybersecurity workflows. It watches your logs, runs scans, tracks missions, learns from interactions, and evolves visually—all powered by **Python**, **LangChain**, **ChromaDB**, and **Ollama**.

## Features

- 🛡 **Real-World Tools**: integrates `nmap`, `ss`, `tail`, `fail2ban`, and more.
- 🎯 **Missions & XP**: complete tasks like network scans to earn experience points and level up.
- 🧠 **Persistent Memory**: stores past interactions and logs in a vector store for AI-powered recall.
- 🤖 **AI Assistant**: chat with Gotchi via Ollama LLM for log analysis, explanations, and guidance.
- 💾 **Plugin System**: extend SecuriGotchi with custom missions and tools without modifying core code.
- 🌈 **ANSI Art Evolution**: dynamic avatars change based on mode and XP level.
- 🚀 **Boot-to-Terminal**: auto-start on boot with systemd for headless operation.
- ⚡ **Threat Monitoring**: live log watcher detects SSH brute-force and sudo misuse events.
- 📊 **Diagnostics Panel**: view CPU, RAM, disk usage, and open ports in a retro HUD style.

## Architecture

```
[ Terminal UI ]       ← console / touchscreen
        ↓
[ gotchi_agent.py ]   → runs core loop, avatars, input handling
        ↓
[ plugin_manager.py ] → discovers and loads mission/tool plugins
        ↓            ↘
[ gotchi_mission.py ]   [ plugin_runner.py ] → executes plugins with XP rewards
        ↓
[ gotchi_brain.json ]  ↔ persistent JSON memory
[ gotchi_memory.py]    ↔ CLI for viewing/editing memory & modes
[ gotchi_ai_config.json ] → AI system prompts & model settings
[ Chroma Vector DB ]   → stores embeddings of logs and AI chats
[ threat_watcher.py ]  → live log monitoring
[ diag_panel.py ]      → diagnostics HUD
[ install.sh ]         → installer script
[ secgotchi.service ]  → systemd autostart unit
```

## Requirements

- **Hardware**: Raspberry Pi 4B (8GB) + 3.5” touchscreen
- **OS**: Kali Linux (minimal / headless optional)
- **Python 3.10+**
- **Dependencies**:
  - `pip install langchain chromadb`
  - `pip install ollama-tools` (if available)
- **CLI Tools**: `nmap`, `ss`/`netstat`, `tail`, `chafa` or `ansilove`, `fbi` (optional)

## Installation

```bash
git clone https://github.com/CptNope/SecuriGotchi.git
cd SecuriGotchi
chmod +x install.sh
./install.sh
```

The installer will:
- Update system packages
- Install Python dependencies
- Install ANSI renderer (`chafa` or `ansilove`)
- Copy `secgotchi.service` to `/etc/systemd/system/`
- Enable and start the service (optional)
- Symlink `gotchi_agent.py` to `/usr/local/bin/gotchi`

## Quick Start

After installation, you can launch SecuriGotchi with:

```bash
gotchi               # Interactive main agent
gotchi diag          # Diagnostics panel
gotchi watch         # Start threat monitor
gotchi memory view   # View brain memory and XP
gotchi memory edit   # Manually edit memory & modes
gotchi mission list  # List available missions
gotchi mission run 1 # Run mission ID 1 and earn XP
python plugin_runner.py # Load and run plugins
```

## Core Commands

| Command                     | Description                                      |
|-----------------------------|--------------------------------------------------|
| `gotchi`                    | Launch main AI-assisted terminal companion       |
| `gotchi diag`               | Show CPU, RAM, disk, and open ports              |
| `gotchi watch`              | Start live threat log monitoring                 |
| `gotchi memory view`        | Display `gotchi_brain.json` contents             |
| `gotchi memory edit`        | Edit memory & modes in your preferred editor     |
| `gotchi mission list`       | List all missions from `missions.json`           |
| `gotchi mission run <id>`   | Execute mission command & award XP               |
| `python plugin_runner.py`   | List and execute plugins (missions & tools)      |

## Configuration Files

- **`gotchi_brain.json`**: stores XP, level, memory logs, mode
- **`gotchi_ai_config.json`**: Ollama model settings (model, temperature, system_prompt)
- **`missions/missions.json`**: mission definitions (id, title, command, xp_reward)

## Missions & XP System

Missions are defined in `missions/missions.json`. Each mission has:
```json
{
  "id": 1,
  "title": "Scan Your Local Network",
  "command": "nmap -T4 -A 192.168.1.0/24",
  "xp_reward": 25,
  "completed": false
}
```
Use `gotchi mission list` and `gotchi mission run <id>` to execute and track progress. XP is automatically added to your brain memory.

## Plugin System

Drop plugins into the `plugins/` directory. Each plugin must have:
- `manifest.json` with:
  - `name`: string
  - `type`: "mission" or "tool"
  - `module`: name of the .py file
  - `description`: string
  - `xp_reward` (for missions): integer
- `<module>.py` implementing a `run()` function.

Use:
```bash
python plugin_runner.py
```
to discover and run plugins.

## Autonomy Modes

| Mode         | Level | Confirm ✓ | Sudo ⚠ |
|--------------|-------|-----------|--------|
| observer     | 0     | No        | No     |
| training     | 1     | Yes       | No     |
| standard     | 2     | Yes       | No     |
| full-control | 3     | No        | Yes    |

Switch modes:
```bash
gotchi memory mode full-control
```

## Memory & AI Assistant

Use **LangChain** + **Ollama** for AI chats and memory:
- **Store Memory**: interactions embedded and saved
- **Chat**: `python gotchi_agent.py`
- **Config**: `gotchi_ai_config.json`

## Threat Monitoring

`gotchi watch` runs `threat_watcher.py`:
- Tails `/var/log/auth.log`
- Detects SSH failures & sudo misuse
- Logs events to memory and awards XP

## Diagnostics Panel

`gotchi diag` runs `diag_panel.py`, displaying system stats.

## Boot-to-Terminal

Enable auto-start:
```bash
sudo systemctl enable secgotchi.service
```

## Contributing

1. Fork the repo
2. Create a branch (`git checkout -b feature/foo`)
3. Commit (`git commit -am 'Add feature'`)
4. Push (`git push origin feature/foo`)
5. Open a PR

## Troubleshooting

- Ensure `gotchi_memory/` exists and is writable
- Confirm `ollama run llama3` works
- Run commands with `sudo` in full-control mode only

## License

MIT © 2025 [CptNope](https://github.com/CptNope)
