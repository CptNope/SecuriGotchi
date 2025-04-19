# SecuriGotchi: Cybersecurity Companion with Blockchain Memory, RAG, and Modular Plugins

**SecuriGotchi** is a cyberpunk-inspired, terminal-based AI companion designed to run on Raspberry Pi, Ubuntu, or WSL with Kali Linux. It combines **gamified missions**, **diagnostics**, **AI chat**, and **immutable blockchain-style memory logging** — now enhanced with **vector search + RAG (Retrieval-Augmented Generation)** for intelligent memory recall.

---

## 📦 Key Features

| Feature                      | Description                                                                 |
|------------------------------|-----------------------------------------------------------------------------|
| 🧠 Memory + XP               | Earn XP and track progress with persistent JSON state                       |
| 🔗 Blockchain Memory         | Immutable memory ledger (`gotchi_chain.json`) with SHA-256 chaining        |
| ✍️ GPG Signing               | Cryptographically signs the memory chain (`gotchi_chain.json.sig`)         |
| 📜 Memory Changelog          | Human-readable XP log (`gotchi_memory_changelog.txt`)                      |
| 🧩 Modular Plugin System     | Drop-in tools and missions extend Gotchi’s abilities                        |
| 🔍 Vector Search (ChromaDB)  | Store and query memory embeddings for similarity retrieval                  |
| 🧠 RAG Memory Recall         | Ask questions and receive contextual memory-based answers                   |
| 🔒 Mode Levels               | Observer → Full-Control autonomy with XP-based access                       |
| ⚠️ Threat Monitor            | Monitors `/var/log/auth.log` for intrusion attempts                         |
| 📊 System Diagnostics        | View CPU, RAM, disk, and open ports in terminal                             |

---

## 📂 Directory Overview

```
.
├── gotchi_brain.json             # Core XP, memory, and autonomy mode
├── gotchi_chain.json             # Blockchain-style immutable XP ledger
├── gotchi_chain.json.sig         # GPG signature of chain
├── gotchi_chain.py               # Chain logic + GPG sign/verify
├── gotchi_memory.py              # Adds memory, XP, vector, and changelog
├── gotchi_memory_changelog.txt   # Human-readable log of memory entries
├── gotchi_vector.py              # Embedding + vector store operations (ChromaDB)
├── gotchi_query.py               # Ask questions via vector + RAG
├── secgotchi_install.sh          # Universal installer (Ubuntu/WSL/RPi)
├── README.md                     # You're reading it
```

---

## 🧠 New AI Features (Vector + RAG)

- All memory entries are embedded and stored in a **vector database**
- Use `gotchi_query.py` to search memory by meaning, not keywords:

```bash
python gotchi_query.py "What scans did I run this week?"
```

- Returns top 3 matches with context-aware results (powered by SentenceTransformers)
- Can integrate with Ollama to generate full natural language responses (optional)

---

## 🧩 Plugin Scope Overview

### 🔍 Recon & Scanning
- `Metasploit Basic Scan`  
- `Nikto Web Scan`  
- `Nmap Top Ports`  
- `Reverse DNS Scan`

### 📡 System Diagnostics
- `Netstat Summary`  
- `Fail2Ban Status`  
- `UID Check`  
- `Environment Vars`

### 🛡 Security + Hardening
- `List SUID Binaries`  
- `SSH Honeypot Check`  
- `User Enumeration`

### 🧪 Tools
- `WHOIS Lookup`  
- `Traceroute Tool`  
- `GeoIP Lookup`  
- `TCPDump Sniffer`

---

## ✅ GPG Setup

Run once:
```bash
gpg --full-generate-key
gpg --list-keys
```

All XP entries are:
- Logged to `gotchi_brain.json`
- Added to `gotchi_chain.json`
- Signed to `gotchi_chain.json.sig`
- Logged in `gotchi_memory_changelog.txt`
- Embedded into the vector DB

---

## 🔍 Validate the Memory Chain

```bash
gpg --verify gotchi_chain.json.sig gotchi_chain.json
```

Or:
```python
from gotchi_chain import validate_chain
print(validate_chain())
```

---

## 🚀 Add an XP Entry

```bash
python gotchi_memory.py "Completed SSH Audit" 25
```

---

## 🧱 Future Features (Planned)

- 🌐 Remote syncing via Git or API
- 🔑 Public key identity system for verifiable Gotchis
- 📦 `.deb` and `.img` install packages
- 🧠 Ollama-based conversation agent (LLM)
- 🕸 Web dashboard with mission logs, threat stats, and gotchi health

---

Built by [Jeremy Anderson](https://jeremyanderson.tech)  
GitHub: [CptNope/SecuriGotchi](https://github.com/CptNope/SecuriGotchi)