# SecuriGotchi — AI-Enhanced Cyberpunk Terminal Companion

SecuriGotchi is a terminal-based AI companion for Raspberry Pi and cybersecurity monitoring, now with persistent memory and LangChain-powered interaction.

## Features

- 🧠 **LangChain Memory** with Ollama + ChromaDB
- 🔐 Real-time auth.log monitoring (`gotchi watch`)
- 🎛️ Diagnostic panel (`gotchi diag`)
- 🧬 Editable autonomy modes (`gotchi memory`)
- 🌈 ANSI avatars evolve with XP & mode
- 🐧 Boot-to-terminal support with `systemd`
- 🛠️ Fully local, offline-compatible

## Install

```bash
pip install langchain chromadb
ollama run llama3
python gotchi_agent.py
```

## Docs

See `docs/index.html` for full usage, screenshots, and CLI help.