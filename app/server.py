import json, platform, shutil, time
from pathlib import Path
import psutil
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from .auth import current_user, require_csrf, require_owner, sign_in, sign_out
from .config import APP_NAME, CSRF_COOKIE_NAME, OWNER_EMAIL, SESSION_COOKIE_NAME, STORAGE_ROOT
from .db import db, init_db
from .security import hash_password, iso, token, token_hash, verify_password
from .storage import delete_path, ensure_dir, resolve_user_path, save_upload, used_bytes

app=FastAPI(title=APP_NAME,docs_url="/api/docs",redoc_url="/api/redoc")
init_db()
DASHBOARD=Path(__file__).resolve().parents[1]/"dashboard"

def audit(actor,action,resource=None,target=None,success=True,metadata=None):
    with db() as conn: conn.execute("INSERT INTO audit_events(actor_id,actor_role,action,resource,target,success,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?)",(actor["id"] if actor else None,actor["role"] if actor else None,action,resource,target,int(success),json.dumps(metadata or {}),iso()))

@app.get("/",include_in_schema=False)
def index(): return FileResponse(DASHBOARD/"index.html")
@app.get("/dashboard/{name}",include_in_schema=False)
def dashboard_asset(name:str):
    if name not in {"app.js","app.css"}: raise HTTPException(404)
    return FileResponse(DASHBOARD/name)
@app.get("/api/health")
def health(): return {"status":"ok","service":APP_NAME}

@app.post("/api/setup")
async def setup(payload:dict,request:Request):
    with db() as conn:
        count=conn.execute("SELECT COUNT(*) c FROM users WHERE status IN ('active','invited','suspended')").fetchone()["c"]
        if count: raise HTTPException(409,"Initial setup has already been completed")
        email=str(payload.get("email","")).strip().lower(); password=str(payload.get("password",""))
        if email!=OWNER_EMAIL: raise HTTPException(400,"Owner email does not match configured owner")
        if len(password)<12: raise HTTPException(400,"Password must be at least 12 characters")
        now=iso(); cur=conn.execute("INSERT INTO users(email,display_name,password_hash,role,status,quota_bytes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(email,"Owner",hash_password(password),"owner","active",0,now,now)); uid=cur.lastrowid
    audit({"id":uid,"role":"owner"},"owner_setup")
    raw,csrf=sign_in(uid,request.headers.get("user-agent",""),request.client.host if request.client else "")
    response=JSONResponse({"ok":True,"csrf":csrf}); secure=request.url.scheme=="https"
    response.set_cookie(SESSION_COOKIE_NAME,raw,httponly=True,secure=secure,samesite="strict",max_age=604800,path="/"); response.set_cookie(CSRF_COOKIE_NAME,csrf,httponly=False,secure=secure,samesite="strict",max_age=604800,path="/")
    return response

@app.post("/api/auth/login")
async def login(payload:dict,request:Request):
    email=str(payload.get("email","")).strip().lower(); password=str(payload.get("password",""))
    with db() as conn: user=conn.execute("SELECT * FROM users WHERE email=? AND status='active'",(email,)).fetchone()
    if not user or not user["password_hash"] or not verify_password(password,user["password_hash"]): audit(None,"login_failed","auth",email,False); raise HTTPException(401,"Invalid credentials")
    raw,csrf=sign_in(user["id"],request.headers.get("user-agent",""),request.client.host if request.client else ""); audit(user,"login_success","auth",email)
    response=JSONResponse({"ok":True,"csrf":csrf,"user":{"id":user["id"],"email":user["email"],"role":user["role"],"display_name":user["display_name"]}}); secure=request.url.scheme=="https"
    response.set_cookie(SESSION_COOKIE_NAME,raw,httponly=True,secure=secure,samesite="strict",max_age=604800,path="/"); response.set_cookie(CSRF_COOKIE_NAME,csrf,httponly=False,secure=secure,samesite="strict",max_age=604800,path="/"); return response

@app.post("/api/auth/logout")
def logout(request:Request):
    user=current_user(request); require_csrf(request,user); sign_out(request); audit(user,"logout","auth"); response=JSONResponse({"ok":True}); response.delete_cookie(SESSION_COOKIE_NAME,path="/"); response.delete_cookie(CSRF_COOKIE_NAME,path="/"); return response
@app.get("/api/auth/me")
def me(request:Request):
    user=current_user(request); return {"id":user["id"],"email":user["email"],"role":user["role"],"display_name":user["display_name"],"csrf":user["csrf_token"]}

@app.get("/api/overview")
def overview(request:Request):
    user=current_user(request); disk=shutil.disk_usage(STORAGE_ROOT); used=used_bytes(user["id"]); quota=int(user["quota_bytes"])
    if user["role"]=="owner":
        with db() as conn: rows=conn.execute("SELECT id,quota_bytes FROM users WHERE status IN ('active','suspended')").fetchall()
        quota=sum(int(r["quota_bytes"]) for r in rows); used=sum(used_bytes(int(r["id"])) for r in rows)
    return {"storage":{"disk_total":disk.total,"disk_free":disk.free,"quota":quota,"used":used,"percent":round(used/quota*100,2) if quota else 0},"system":{"cpu_percent":psutil.cpu_percent(interval=.05),"ram_percent":psutil.virtual_memory().percent,"uptime_seconds":int(time.time()-psutil.boot_time()),"platform":platform.platform()}}

@app.get("/api/files")
def list_files(request:Request,path:str=""):
    user=current_user(request); target=resolve_user_path(user["id"],path)
    if not target.exists() or not target.is_dir(): raise HTTPException(404,"Directory not found")
    root=resolve_user_path(user["id"],""); items=[]
    for p in sorted(target.iterdir(),key=lambda x:(not x.is_dir(),x.name.lower())):
        rel=str(p.relative_to(root)); stat=p.stat(); items.append({"name":p.name,"path":rel,"is_dir":p.is_dir(),"size":stat.st_size if p.is_file() else 0,"modified":stat.st_mtime})
    return {"path":path,"items":items}
@app.post("/api/files/folder")
def folder(request:Request,payload:dict):
    user=current_user(request); require_csrf(request,user); path=str(payload.get("path","")); result=ensure_dir(user["id"],path); audit(user,"folder_create","file",path); return result
@app.post("/api/files/upload")
async def upload(request:Request,file:UploadFile=File(...),path:str=Form("")):
    user=current_user(request); require_csrf(request,user); relative=str(Path(path)/file.filename); result=await save_upload(user["id"],relative,file); audit(user,"file_upload","file",relative,metadata={"size":result["size_bytes"]}); return result
@app.get("/api/files/download")
def download(request:Request,path:str):
    user=current_user(request); target=resolve_user_path(user["id"],path)
    if not target.exists() or not target.is_file(): raise HTTPException(404,"File not found")
    audit(user,"file_download","file",path); return FileResponse(target,filename=target.name)
@app.delete("/api/files")
def remove(request:Request,path:str):
    user=current_user(request); require_csrf(request,user); result=delete_path(user["id"],path); audit(user,"file_delete","file",path); return result

@app.get("/api/users")
def users(request:Request):
    user=current_user(request); require_owner(user)
    with db() as conn: rows=conn.execute("SELECT id,email,display_name,role,status,quota_bytes,created_at,updated_at FROM users WHERE status!='removed' ORDER BY id").fetchall()
    return {"users":[dict(r) for r in rows]}
@app.patch("/api/users/{user_id}")
def update_user(user_id:int,request:Request,payload:dict):
    actor=current_user(request); require_owner(actor); require_csrf(request,actor)
    if user_id==actor["id"]: raise HTTPException(400,"Owner cannot be modified through user admin")
    with db() as conn: target=conn.execute("SELECT * FROM users WHERE id=? AND role='user'",(user_id,)).fetchone()
    if not target: raise HTTPException(404,"User #2 not found")
    updates=[]; values=[]
    if "quota_bytes" in payload:
        quota=int(payload["quota_bytes"])
        if quota<used_bytes(user_id): raise HTTPException(409,"Quota cannot be lower than current usage")
        updates += ["quota_bytes=?"]; values += [quota]
    if payload.get("status") in {"active","suspended","removed"}: updates += ["status=?"]; values += [payload["status"]]
    if not updates: raise HTTPException(400,"No supported changes")
    with db() as conn: conn.execute("UPDATE users SET "+",".join(updates)+",updated_at=? WHERE id=?",(*values,iso(),user_id))
    audit(actor,"user_update","user",str(user_id),metadata=payload); return {"ok":True}
@app.post("/api/users/invite")
def invite(request:Request,payload:dict):
    actor=current_user(request); require_owner(actor); require_csrf(request,actor); email=str(payload.get("email","")).strip().lower(); name=str(payload.get("display_name","User #2")).strip() or "User #2"; quota=int(payload.get("quota_bytes",0))
    if not email or quota<0: raise HTTPException(400,"Invalid invitation")
    with db() as conn:
        count=conn.execute("SELECT COUNT(*) c FROM users WHERE status IN ('active','invited','suspended')").fetchone()["c"]
        if count>=2: raise HTTPException(409,"User limit reached")
        if conn.execute("SELECT id FROM users WHERE email=? AND status!='removed'",(email,)).fetchone(): raise HTTPException(409,"Account already exists")
        raw=token(); conn.execute("INSERT INTO invitations(email,display_name,token_hash,quota_bytes,expires_at,created_at) VALUES(?,?,?,?,?,?)",(email,name,token_hash(raw),quota,iso(),iso()))
    audit(actor,"user_invite","invitation",email); return {"ok":True,"invitation_token":raw}
@app.post("/api/invitations/accept")
def accept(payload:dict):
    raw=str(payload.get("token","")); password=str(payload.get("password",""))
    if len(password)<12: raise HTTPException(400,"Password must be at least 12 characters")
    with db() as conn:
        inv=conn.execute("SELECT * FROM invitations WHERE token_hash=? AND accepted_at IS NULL AND revoked_at IS NULL",(token_hash(raw),)).fetchone()
        if not inv: raise HTTPException(400,"Invalid invitation")
        active=conn.execute("SELECT COUNT(*) c FROM users WHERE status IN ('active','invited','suspended')").fetchone()["c"]
        if active>=2: raise HTTPException(409,"User limit reached")
        now=iso(); cur=conn.execute("INSERT INTO users(email,display_name,password_hash,role,status,quota_bytes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(inv["email"],inv["display_name"],hash_password(password),"user","active",inv["quota_bytes"],now,now)); conn.execute("UPDATE invitations SET accepted_at=? WHERE id=?",(now,inv["id"]))
    audit({"id":cur.lastrowid,"role":"user"},"invitation_accepted","user",inv["email"]); return {"ok":True}

@app.get("/api/audit")
def audit_log(request:Request,limit:int=100):
    user=current_user(request); require_owner(user)
    with db() as conn: rows=conn.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT ?",(min(limit,500),)).fetchall()
    return {"events":[dict(r) for r in rows]}
@app.get("/api/diagnostics")
def diagnostics(request:Request):
    user=current_user(request); require_owner(user); disk=shutil.disk_usage(STORAGE_ROOT); used=100-(disk.free/disk.total*100)
    return {"checks":[{"name":"database","status":"PASS","detail":"SQLite available"},{"name":"storage","status":"PASS","detail":str(STORAGE_ROOT)},{"name":"disk","status":"CRITICAL" if used>=95 else "WARNING" if used>=90 else "PASS","detail":f"{used:.1f}% used"},{"name":"memory","status":"WARNING" if psutil.virtual_memory().percent>=90 else "PASS","detail":f"{psutil.virtual_memory().percent:.1f}% used"}]}
@app.get("/api/terminal")
def terminal_status(request:Request):
    user=current_user(request); require_owner(user); return {"enabled":False,"message":"Web terminal is disabled by default."}
