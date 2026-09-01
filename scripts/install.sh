#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -z "${PREFIX:-}" ] || [ ! -d "$PREFIX" ]; then echo "This installer must run inside Termux."; exit 1; fi
pkg update -y
pkg install -y python nginx sqlite git curl openssl
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
mkdir -p data storage users projects apps websites databases backups logs runtime deployments secrets
if [ ! -f .env ]; then cp .env.example .env; SECRET="$(openssl rand -hex 32)"; sed -i "s#^SERVER_SECRET=.*#SERVER_SECRET=$SECRET#" .env; fi
echo "Installation complete. Run: . .venv/bin/activate && python -m app"