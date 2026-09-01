#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -f runtime/server.pid ]; then kill "$(cat runtime/server.pid)" 2>/dev/null || true; rm -f runtime/server.pid; fi
