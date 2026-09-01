from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]

def path_env(name: str, default: str) -> Path:
    value = os.getenv(name, default)
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path

APP_NAME = os.getenv("APP_NAME", "Roshab Android Termux Server")
APP_ENV = os.getenv("APP_ENV", "production")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))
DATABASE_PATH = path_env("DATABASE_PATH", "./data/server.db")
STORAGE_ROOT = path_env("STORAGE_ROOT", "./storage")
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "168"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "2048"))
RESERVED_STORAGE_GB = float(os.getenv("RESERVED_STORAGE_GB", "4"))
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "roshabbhandari1334@gmail.com").strip().lower()
SERVER_SECRET = os.getenv("SERVER_SECRET", "")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "rt_session")
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "rt_csrf")

for directory in [DATABASE_PATH.parent, STORAGE_ROOT, ROOT / "runtime", ROOT / "logs", ROOT / "backups", ROOT / "deployments", ROOT / "secrets"]:
    directory.mkdir(parents=True, exist_ok=True)

if APP_ENV == "production" and len(SERVER_SECRET) < 32:
    raise RuntimeError("SERVER_SECRET must be at least 32 characters in production")
