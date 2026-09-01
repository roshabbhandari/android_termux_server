#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
curl -fsS http://127.0.0.1:8080/api/health >/dev/null
echo "server: PASS"
