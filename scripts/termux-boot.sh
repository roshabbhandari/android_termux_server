#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/roshab-server"
cd "$ROOT"
sleep 15
nohup "$ROOT/scripts/start.sh" >> "$ROOT/logs/boot.log" 2>&1 &
