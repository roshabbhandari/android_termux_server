# Architecture

```text
Internet
  |
Cloudflare Tunnel (optional; stable hostname requires a domain)
  |
Nginx
  |
FastAPI control plane :8080
  |---- SQLite metadata
  |---- isolated user storage
  |---- projects / app metadata
  |---- audit events
```

The control plane is intentionally lightweight: SQLite, one Uvicorn process, Python standard-library password hashing, psutil, and a vanilla dashboard. Docker/Kubernetes are not required.

SQLite is the default project database. PostgreSQL/MariaDB are optional future managed services rather than mandatory daemons on the phone.

All storage paths resolve beneath a user-specific root. The owner role is the only administrative role. The active-account model is capped at one owner plus one non-owner account.

A powered-off Redmi cannot serve traffic. Recovery only restores service after Android, Termux, networking, and the server process are back.

## Tunnel limitation

Cloudflare Quick Tunnels use random temporary `trycloudflare.com` hostnames. Stable named Tunnel hostnames require a domain/zone. The repository therefore keeps tunnel configuration separate and does not pretend a quick URL is permanent.
