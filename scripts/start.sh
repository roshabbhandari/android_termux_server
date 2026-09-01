#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
. .venv/bin/activate
mkdir -p logs runtime
if [ -f runtime/server.pid ] && kill -0 "$(cat runtime/server.pid)" 2>/dev/null; then exit 0; fi
nohup python -m app >> logs/server.log 2>&1 &
echo $! > runtime/server.pid
