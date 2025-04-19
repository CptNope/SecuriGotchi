#!/bin/bash

echo "🧠 SecuriGotchi Universal Installer for Ubuntu/WSL"

# Update and install packages
echo "📦 Installing required system packages..."
sudo apt update && sudo apt install -y \
    nmap tcpdump net-tools fail2ban \
    geoip-bin whois traceroute gnupg \
    python3 python3-pip

echo "🐍 Installing Python libraries..."
pip3 install --upgrade pip
pip3 install langchain chromadb sentence-transformers

# Clone the GitHub repo
if [ ! -d "SecuriGotchi" ]; then
    echo "⬇️ Cloning SecuriGotchi repository..."
    git clone https://github.com/CptNope/SecuriGotchi.git
fi

cd SecuriGotchi

# Setup blockchain files if not present
if [ ! -f gotchi_brain.json ]; then
    echo "🧠 Creating initial brain..."
    cat > gotchi_brain.json <<EOF
{
  "xp": 0,
  "level": 1,
  "last_command": "",
  "memory_log": [],
  "notes": "Blockchain memory enabled",
  "mode": {
    "name": "observer",
    "autonomy_level": 0,
    "confirm_commands": true,
    "allow_sudo": false
  }
}
EOF
fi

if [ ! -f gotchi_chain.json ]; then
    echo "🔗 Creating genesis block..."
    python3 -c "from gotchi_chain import load_chain; load_chain()"
fi

# Check for GPG key
echo "🔐 Checking for GPG key..."
if ! gpg --list-keys | grep -q sec; then
    echo "⚠️ No GPG key found. Launching key generation..."
    gpg --full-generate-key
fi

# Create CLI shortcut
echo "🔗 Linking gotchi-log..."
sudo ln -sf $(pwd)/gotchi_memory.py /usr/local/bin/gotchi-log

echo "✅ SecuriGotchi installation complete with RAG + vector search."