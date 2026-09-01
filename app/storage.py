import hashlib
import mimetypes
import shutil
from pathlib import Path
from fastapi import HTTPException, UploadFile
from .config import STORAGE_ROOT, MAX_UPLOAD_MB
from .db import db
from .security import iso

def user_root(user_id: int) -> Path:
    root = STORAGE_ROOT / "users" / str(user_id)
    root.mkdir(parents=True, exist_ok=True)
    return root

def safe_relative(value: str) -> Path:
    value = value.replace("\\", "/").lstrip("/")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise HTTPException(400, "Invalid path")
    return path

def resolve_user_path(user_id: int, relative: str) -> Path:
    root = user_root(user_id).resolve()
    candidate = (root / safe_relative(relative)).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(400, "Path escapes storage root")
    return candidate

def used_bytes(user_id: int) -> int:
    root = user_root(user_id)
    total = 0
    for path in root.rglob("*"):
        if path.is_file():
            try: total += path.stat().st_size
            except OSError: pass
    return total

def quota_bytes(user_id: int) -> int:
    with db() as conn:
        row = conn.execute("SELECT quota_bytes FROM users WHERE id=?", (user_id,)).fetchone()
        return int(row["quota_bytes"]) if row else 0

def check_quota(user_id: int, incoming: int):
    quota = quota_bytes(user_id)
    if quota and used_bytes(user_id) + incoming > quota:
        raise HTTPException(413, "Storage quota exceeded")

async def save_upload(user_id: int, relative: str, upload: UploadFile):
    target = resolve_user_path(user_id, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.is_dir(): raise HTTPException(409, "Target is a directory")
    tmp = target.with_name(target.name + ".uploading")
    written = 0; digest = hashlib.sha256(); limit = MAX_UPLOAD_MB * 1024 * 1024
    try:
        with tmp.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk: break
                written += len(chunk)
                if written > limit: raise HTTPException(413, "Upload exceeds configured maximum")
                check_quota(user_id, len(chunk)); handle.write(chunk); digest.update(chunk)
        tmp.replace(target)
    except Exception:
        tmp.unlink(missing_ok=True); raise
    with db() as conn:
        rel = str(target.relative_to(user_root(user_id)))
        conn.execute("INSERT INTO files(owner_id,name,relative_path,is_dir,size_bytes,mime_type,sha256,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (user_id,target.name,rel,0,written,mimetypes.guess_type(target.name)[0],digest.hexdigest(),iso(),iso()))
    return {"name": target.name, "path": rel, "size_bytes": written, "sha256": digest.hexdigest()}

def ensure_dir(user_id: int, relative: str):
    target = resolve_user_path(user_id, relative); target.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        rel = str(safe_relative(relative))
        exists = conn.execute("SELECT id FROM files WHERE owner_id=? AND relative_path=? AND deleted_at IS NULL", (user_id,rel)).fetchone()
        if not exists: conn.execute("INSERT INTO files(owner_id,name,relative_path,is_dir,created_at,updated_at) VALUES(?,?,?,?,?,?)", (user_id,target.name or "root",rel,1,iso(),iso()))
    return {"path": rel}

def delete_path(user_id: int, relative: str):
    target = resolve_user_path(user_id, relative)
    if target == user_root(user_id): raise HTTPException(400, "Cannot delete storage root")
    if not target.exists(): raise HTTPException(404, "File not found")
    trash = STORAGE_ROOT / ".trash" / str(user_id); trash.mkdir(parents=True, exist_ok=True)
    destination = trash / (hashlib.sha256((relative + iso()).encode()).hexdigest() + "-" + target.name)
    shutil.move(str(target), str(destination))
    rel = str(safe_relative(relative))
    with db() as conn:
        conn.execute("UPDATE files SET deleted_at=? WHERE owner_id=? AND (relative_path=? OR relative_path LIKE ?)", (iso(),user_id,rel,rel+"/%"))
    return {"deleted": True}
