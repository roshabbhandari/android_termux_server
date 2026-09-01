import sqlite3
from contextlib import contextmanager
from .config import DATABASE_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT NOT NULL UNIQUE,display_name TEXT NOT NULL,password_hash TEXT,role TEXT NOT NULL CHECK(role IN ('owner','user')),status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended','removed','invited')),quota_bytes INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,token_hash TEXT NOT NULL UNIQUE,csrf_token TEXT NOT NULL,created_at TEXT NOT NULL,last_activity TEXT NOT NULL,expires_at TEXT NOT NULL,user_agent TEXT,ip_address TEXT);
CREATE TABLE IF NOT EXISTS invitations (id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT NOT NULL,display_name TEXT NOT NULL,token_hash TEXT NOT NULL UNIQUE,quota_bytes INTEGER NOT NULL,expires_at TEXT NOT NULL,accepted_at TEXT,revoked_at TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,project_id INTEGER,parent_id INTEGER REFERENCES files(id) ON DELETE CASCADE,name TEXT NOT NULL,relative_path TEXT NOT NULL,is_dir INTEGER NOT NULL DEFAULT 0,size_bytes INTEGER NOT NULL DEFAULT 0,mime_type TEXT,sha256 TEXT,deleted_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,slug TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',storage_quota_bytes INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(owner_id,slug));
CREATE TABLE IF NOT EXISTS audit_events (id INTEGER PRIMARY KEY AUTOINCREMENT,actor_id INTEGER,actor_role TEXT,action TEXT NOT NULL,resource TEXT,target TEXT,success INTEGER NOT NULL DEFAULT 1,metadata_json TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS app_services (id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,name TEXT NOT NULL,kind TEXT NOT NULL,directory TEXT NOT NULL,command_json TEXT,port INTEGER,status TEXT NOT NULL DEFAULT 'stopped',restart_count INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS databases (id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,name TEXT NOT NULL,engine TEXT NOT NULL DEFAULT 'sqlite',path TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS backups (id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER,kind TEXT NOT NULL,path TEXT NOT NULL,size_bytes INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scheduled_jobs (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,kind TEXT NOT NULL,cron TEXT,enabled INTEGER NOT NULL DEFAULT 1,config_json TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS server_settings (key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_files_owner_parent ON files(owner_id,parent_id);
CREATE INDEX IF NOT EXISTS idx_files_owner_deleted ON files(owner_id,deleted_at);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at);
"""

@contextmanager
def db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)
