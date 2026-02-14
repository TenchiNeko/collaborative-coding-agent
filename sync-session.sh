#!/bin/bash
# sync-session.sh — Push completed session from Cortana to PVE node
# Called automatically by the orchestrator after each run, or manually:
#   bash sync-session.sh /tmp/bookmark-v100
#
# Also pulls the latest playbook.json back from PVE.

set -e

SESSION_DIR="$1"
PVE_HOST="${PVE_HOST:-100.81.200.82}"  # Tailscale IP for homeserver
PVE_USER="${PVE_USER:-brandon}"
SHARED="/shared"

if [ -z "$SESSION_DIR" ]; then
    echo "Usage: $0 <session-dir>"
    echo "  e.g.: $0 /tmp/bookmark-v100"
    exit 1
fi

if [ ! -d "$SESSION_DIR" ]; then
    echo "❌ Directory not found: $SESSION_DIR"
    exit 1
fi

SESSION_ID=$(basename "$SESSION_DIR")

# --- Check if session is complete ---
if [ ! -f "$SESSION_DIR/.agents/state.json" ]; then
    echo "⚠️  No state.json found in $SESSION_DIR — session may not be complete"
fi

# --- Push session to PVE ---
echo "📤 Syncing session $SESSION_ID to PVE node..."
rsync -az --timeout=30 \
    --include='.agents/***' \
    --include='*.py' \
    --exclude='venv/***' \
    --exclude='__pycache__/***' \
    --exclude='.git/***' \
    "$SESSION_DIR/" "$PVE_USER@$PVE_HOST:$SHARED/sessions/$SESSION_ID/"

echo "✅ Session synced: $PVE_USER@$PVE_HOST:$SHARED/sessions/$SESSION_ID"

# --- Pull latest playbook back ---
echo "📥 Pulling latest playbook from PVE..."
ORCH_DIR="$(cd "$(dirname "$0")" && pwd)"
rsync -az --timeout=10 \
    "$PVE_USER@$PVE_HOST:$SHARED/playbook.json" \
    "$ORCH_DIR/playbook.json" 2>/dev/null || echo "  (no playbook yet — daemon hasn't created one)"

if [ -f "$ORCH_DIR/playbook.json" ]; then
    BULLETS=$(python3 -c "import json; d=json.load(open('$ORCH_DIR/playbook.json')); print(sum(len(v) for v in d.get('sections',{}).values()))" 2>/dev/null || echo "?")
    echo "✅ Playbook pulled: $BULLETS bullets"
fi
