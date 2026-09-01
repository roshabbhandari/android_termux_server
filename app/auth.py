from fastapi import HTTPException, Request
from .config import SESSION_COOKIE_NAME, SESSION_TTL_HOURS
from .db import db
from .security import csrf_token, iso, session_expiry, token, token_hash

def current_user(request: Request):
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw: raise HTTPException(401, "Authentication required")
    with db() as conn:
        row = conn.execute("SELECT u.*,s.id session_id,s.csrf_token,s.expires_at FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.status='active'", (token_hash(raw),iso())).fetchone()
        if not row: raise HTTPException(401, "Session expired")
        conn.execute("UPDATE sessions SET last_activity=? WHERE id=?", (iso(),row["session_id"]))
        return row

def require_csrf(request: Request, user):
    if request.method in {"GET","HEAD","OPTIONS"}: return
    if request.headers.get("X-CSRF-Token") != user["csrf_token"]: raise HTTPException(403,"CSRF validation failed")

def require_owner(user):
    if user["role"] != "owner": raise HTTPException(403,"Owner access required")

def sign_in(user_id: int, user_agent: str, ip: str):
    raw=token(); csrf=csrf_token(); expires=session_expiry(SESSION_TTL_HOURS)
    with db() as conn:
        conn.execute("INSERT INTO sessions(user_id,token_hash,csrf_token,created_at,last_activity,expires_at,user_agent,ip_address) VALUES(?,?,?,?,?,?,?,?)", (user_id,token_hash(raw),csrf,iso(),iso(),iso(expires),user_agent[:500],ip[:100]))
    return raw,csrf

def sign_out(request: Request):
    raw=request.cookies.get(SESSION_COOKIE_NAME)
    if raw:
        with db() as conn: conn.execute("DELETE FROM sessions WHERE token_hash=?",(token_hash(raw),))
