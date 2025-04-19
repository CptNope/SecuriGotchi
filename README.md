# SecuriGotchi: Cybersecurity Companion with Blockchain Memory & Modular Plugins

SecuriGotchi is a cyberpunk-inspired, terminal-based AI companion designed to run on Raspberry Pi with Kali Linux. It combines gamified missions, diagnostics, AI chat, and immutable memory logging via a blockchain-style chain—with GPG signing and modular plugin support.

---

## 📦 Key Features

| Feature                      | Description                                                                 |
|------------------------------|-----------------------------------------------------------------------------|
| 🧠 Memory + XP               | Earn XP and track progress with persistent state                            |
| 🔗 Blockchain Memory         | Immutable chain (`gotchi_chain.json`) of XP events                         |
| ✍️ GPG Signing               | Cryptographically signed chain using GPG (`.sig` file)                      |
| 📜 Memory Changelog          | Human-readable memory entries (`gotchi_memory_changelog.txt`)              |
| ⚙️ Modular Plugin System     | Easily drop in tools or missions to expand Gotchi’s abilities              |
| 🧩 Missions + Tools          | Mix of scanning, monitoring, recon, and reporting capabilities             |
| 🔒 Mode Levels               | Observer → Full-Control autonomy system                                     |
| 📊 System Diagnostics        | Built-in RAM, CPU, disk, and open port reports                              |
| ⚠️ Threat Monitor            | Watches `/var/log/auth.log` for brute-force and sudo misuse attempts       |

---

## 📂 Directory Overview

```
.
├── gotchi_brain.json             # Core memory + XP + mode
├── gotchi_chain.json             # Immutable blockchain-style XP ledger
├── gotchi_chain.json.sig         # GPG signature of chain
├── gotchi_chain.py               # Blockchain logic + validation + signing
├── gotchi_memory.py              # XP entry + changelog integration
├── gotchi_memory_changelog.txt   # Human-readable log
├── README.md                     # You're reading it
```

---

## 🧩 Plugin Scope Overview

### 🔍 Recon & Scanning

- **Metasploit Basic Scan**: Portscan via msfconsole
- **Nikto Web Scan**: Detect web vulns on localhost
- **Nmap Top Ports**: Scan top 1000 ports on subnet
- **Reverse DNS Scan**: `nmap -sL` lookup by IP range

---

### 📡 System Diagnostics

- **Netstat Summary**: TCP/UDP port summary
- **Fail2Ban Status**: View active jails and blocks
- **UID Check**: Show users with UID < 1000
- **Environment Vars**: Dump common env variables

---

### 🛡 Security + Hardening

- **List SUID Binaries**: Find files with `suid` bit
- **SSH Honeypot Check**: Look for brute-force login attempts
- **User Enumeration**: List user logins and accounts

---

### 🧪 Tools

- **WHOIS Lookup**: Domain metadata
- **Traceroute Tool**: Route path analysis
- **GeoIP Lookup**: IP geolocation
- **TCPDump Sniffer**: Live packet capture

---

## ✅ GPG Setup

1. Run this once:
```bash
gpg --full-generate-key
gpg --list-keys
```

2. Every XP entry gets:
- Added to `gotchi_brain.json`
- Appended to `gotchi_chain.json`
- Signed to `gotchi_chain.json.sig`
- Logged to `gotchi_memory_changelog.txt`

---

## 🔍 Validating the Chain

```bash
gpg --verify gotchi_chain.json.sig gotchi_chain.json
```

Or in Python:
```python
from gotchi_chain import validate_chain
print(validate_chain())  # Should return True
```

---

## 🚀 Add an XP Entry

```bash
python gotchi_memory.py "Completed SSH Audit" 25
```

---

## 🧱 Future Features (Planned)

- 🌐 Remote syncing over Git
- 🌎 Public gotchi identity keys
- 📦 Package installer (`.deb`)
- 🕸 Web dashboard (Flask UI)
- 🧠 LLM model checkpointing / fine-tuning logs

---

Built by [Jeremy Anderson](https://jeremyanderson.tech) | GitHub: [CptNope](https://github.com/CptNope)