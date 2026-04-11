# PensHub — AGL App Store

> **Research project** by the [Pervasive Computing Research Group](https://pens.ac.id) at **Politeknik Elektronika Negeri Surabaya (PENS)**, developing an Application Store for **Automotive Grade Linux (AGL)** deployed to the In-Vehicle Infotainment system built by **PENS Electric Vehicle Research**.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Caddy (TLS)                      │
│  agl-store.cyou │ api.* │ hub.* │ repo.* │ admin.* │
└────┬──────┬──────┬──────┬───────┴─────────────────┘
     │      │      │      │
  frontend  │    rest   flat-manager ←── OSTree repo
 (Next.js) admin (FastAPI)   ↑               ↑
          (Next.js)    postgres         repo-server
                              ↑              (nginx)
                         app/backend
                          (gRPC)
```

## Quick Start (new server)

```bash
# 1. Clone
git clone https://github.com/mukhayyar/backend-agl-app-store penshub
cd penshub

# 2. Configure
cp .env.example .env
# edit .env — set DOMAIN, DB_PASSWORD, API_SECRET, JWT_SECRET_KEY, etc.

# 3. Add TLS certs (Cloudflare Origin Certificates)
mkdir -p certs
# copy cf_origin.crt and cf_origin.key to ./certs/

# 4. First-time setup (GPG key, flat-manager binaries, JWT token)
./setup.sh

# 5. Deploy
./deploy.sh
```

## Migrate from another server

```bash
# On old server
./backup.sh                          # creates agl-backup-YYYYMMDD.tar.gz

# On new server
git clone https://github.com/mukhayyar/backend-agl-app-store penshub
cd penshub
./restore.sh /path/to/agl-backup-YYYYMMDD.tar.gz
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| `frontend` | 3000 | Next.js user-facing store |
| `admin` | 3001 | Next.js admin backoffice |
| `rest` | 8002 | FastAPI REST API |
| `backend` | 50051 | Python gRPC server |
| `flat-manager` | 8080 | Flatpak build/publish manager |
| `repo-server` | 80 | nginx OSTree repository |
| `postgres` | 5432 | PostgreSQL 17 |
| `caddy` | 80/443 | Reverse proxy + TLS |

## Automated Jobs (systemd timers)

| Timer | Schedule | Action |
|-------|----------|--------|
| `agl-expiry-check` | Daily 02:00 | Unpublish expired apps, remove from OSTree |
| `agl-repo-rebuild` | Every 30 min | Rebuild Flatpak deltas + regenerate AppStream |
| `agl-ivi-push` | Every 10 min | Auto-push Flutter IVI app to GitHub |

## Security Scanning

Each submitted Flatpak is scanned by:
- **ClamAV** (daemon mode — instant) — malware detection
- **Trivy** — CVE scan on bundled libraries
- **checksec** — ELF binary hardening flags
- **Static manifest analysis** — dangerous permissions, suspicious build commands

Verdict: `PASS` / `WARN` / `BLOCK` (BLOCK auto-notifies admin via Telegram)

## Environment Variables

See `.env.example` for all required variables.

---

*Politeknik Elektronika Negeri Surabaya — Pervasive Computing Research Group*
