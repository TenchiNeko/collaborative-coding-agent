#!/bin/bash
# Deploy the subconscious daemon
# Run this script on the PVE node (homeserver)

set -e

echo "🧠 Deploying Subconscious Daemon"
echo "================================="

# --- Config ---
INSTALL_DIR="/opt/subconscious"
SHARED_DIR="/shared"
SERVICE_NAME="subconscious"
DAEMON_USER="brandon"

# --- Create directories ---
echo "Creating directories..."
sudo mkdir -p "$INSTALL_DIR"
sudo mkdir -p "$SHARED_DIR"/{sessions,training/{queue,ready,used},benchmarks,models/{archive,active,baseline},daemon/feedback}
sudo chown -R "$DAEMON_USER":"$DAEMON_USER" "$SHARED_DIR"
sudo chown -R "$DAEMON_USER":"$DAEMON_USER" "$INSTALL_DIR"

# --- Install daemon files ---
echo "Installing daemon files..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR"/daemon.py "$INSTALL_DIR/"
cp "$SCRIPT_DIR"/config.py "$INSTALL_DIR/"
cp "$SCRIPT_DIR"/playbook.py "$INSTALL_DIR/"
cp "$SCRIPT_DIR"/ollama_client.py "$INSTALL_DIR/"
cp "$SCRIPT_DIR"/session_scanner.py "$INSTALL_DIR/"

# --- Install Python dependencies ---
echo "Installing dependencies..."
pip install httpx --break-system-packages -q 2>/dev/null || pip install httpx -q

# --- Install systemd service ---
echo "Installing systemd service..."
# Generate service file with correct user
cat > /tmp/subconscious.service << SVCEOF
[Unit]
Description=Subconscious Daemon - Autonomous Self-Improving Agent
After=network.target ollama.service

[Service]
Type=simple
User=$DAEMON_USER
Group=$DAEMON_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/daemon.py
Restart=on-failure
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVCEOF

sudo cp /tmp/subconscious.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo ""
echo "✅ Daemon installed to $INSTALL_DIR"
echo "✅ Shared storage at $SHARED_DIR"
echo "✅ Systemd service installed (user: $DAEMON_USER)"
echo ""
echo "--- Next steps ---"
echo "1. Make sure Ollama is running with your 7B/9B model:"
echo "   ollama run qwen2.5-coder:7b"
echo ""
echo "2. Start the daemon:"
echo "   sudo systemctl restart subconscious"
echo "   sudo journalctl -fu subconscious"
echo ""
echo "3. On CORTANA, run the sync setup:"
echo "   bash setup-cortana-sync.sh"
