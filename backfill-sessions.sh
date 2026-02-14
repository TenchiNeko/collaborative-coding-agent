#!/bin/bash
# backfill-sessions.sh — Sync all existing benchmark sessions to PVE node
# Run on Cortana: bash backfill-sessions.sh

SYNC_SCRIPT="$(dirname "$0")/sync-session.sh"

if [ ! -f "$SYNC_SCRIPT" ]; then
    echo "❌ sync-session.sh not found at $SYNC_SCRIPT"
    exit 1
fi

echo "📦 Backfilling existing sessions to PVE node..."
echo ""

count=0
for d in /tmp/bookmark-*/; do
    if [ -d "$d" ] && [ -f "$d/.agents/state.json" ]; then
        echo "--- $(basename "$d") ---"
        bash "$SYNC_SCRIPT" "$d"
        count=$((count + 1))
        echo ""
    fi
done

if [ $count -eq 0 ]; then
    echo "No completed sessions found in /tmp/bookmark-*"
    echo "Run a benchmark first, then backfill."
else
    echo "✅ Backfilled $count sessions"
    echo ""
    echo "Check PVE daemon: sudo journalctl -fu subconscious"
    echo "It should start analyzing within 30 seconds."
fi
