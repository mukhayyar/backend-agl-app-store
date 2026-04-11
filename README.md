# PENS AGL App Store Backend

Backend server for the PENS Automotive Grade Linux (AGL) Application Store. Runs a dual-protocol architecture with HTTP (FastAPI) and gRPC, backed by PostgreSQL and integrated with [flat-manager](https://github.com/niclasr/flat-manager) for Flatpak build publishing.

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start (Docker)](#quick-start-docker)
- [Manual Setup](#manual-setup)
- [Configuration Reference](#configuration-reference)
- [Database Migrations](#database-migrations)
- [Generating Tokens](#generating-tokens)
- [API Documentation](#api-documentation)
- [Deployment to Production](#deployment-to-production)
- [Health Checks](#health-checks)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
                    +-----------------------------------------+
                    |            Backend Server                |
                    |                                         |
  HTTP :8000  ------+  FastAPI (gunicorn + uvicorn)           |
                    |    /http/agl/*    AGL Store API         |
                    |    /http/flathub/* Flathub Proxy        |
                    |                                         |
  gRPC :50051 ------+  gRPC Server (grpcio)                  |
                    |    106 RPC endpoints                    |
                    +--------------+--------------------------+
                                   |
                   +---------------+---------------+
                   v               v               v
              PostgreSQL      flat-manager     Flathub.org
              (database)      (build server)   (proxy target)
```

**Key components:**

| Component | Purpose |
|-----------|---------|
| `main.py` | Entry point -- starts both HTTP and gRPC servers |
| `app/http/` | FastAPI routes, middleware, CORS, rate limiting |
| `app/grpc/` | gRPC server wrapper |
| `app/core/` | Config, JWT auth, RBAC (User/Publisher/Reviewer/Admin) |
| `app/services/` | Clients for flat-manager and Flathub APIs |
| `database.py` | SQLAlchemy models and DB session factory |
| `service.py` | gRPC service implementation |

---

## Prerequisites

- **Python** 3.9+
- **PostgreSQL** 15+ (or 17 via Docker)
- **Docker** and **Docker Compose** (for containerized deployment)
- **flat-manager** instance (for Flatpak build management)

---

## Quick Start (Docker)

This is the recommended way to deploy.

### 1. Clone and configure

```bash
git clone <repository-url>
cd backend
cp .env.example .env
```

### 2. Generate secrets

```bash
# Generate JWT secret key
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Generate flat-manager secret (base64-encoded)
python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

### 3. Edit `.env` with your values

At minimum, you **must** set these variables (the server will refuse to start without them):

```env
# Database
DATABASE_URL=postgresql://youruser:yourpassword@postgres:5432/agl_store
POSTGRES_USER=youruser
POSTGRES_PASSWORD=yourpassword

# Security (REQUIRED -- server will abort if missing or insecure)
JWT_SECRET_KEY=<paste generated key here>
FLAT_MANAGER_SECRET=<paste generated key here>

# CORS -- your frontend URL(s), comma-separated
CORS_ORIGINS=https://your-frontend-domain.com
```

### 4. Start services

```bash
docker compose up -d
```

### 5. Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

### 6. Verify

```bash
# Health check
curl http://localhost:8000/http/health

# Should return: {"status":"healthy","service":"http","database":"ok"}
```

The API docs are available at `http://localhost:8000/http/docs`.

---

## Manual Setup

Use this for local development or non-Docker environments.

### 1. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up PostgreSQL

Create the database and user:

```sql
CREATE USER youruser WITH PASSWORD 'yourpassword';
CREATE DATABASE agl_store OWNER youruser;
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your database URL and secrets (see step 2-3 in Quick Start above)
```

### 5. Generate gRPC code (if not already generated)

```bash
bash build_proto.sh
```

### 6. Run database migrations

```bash
alembic upgrade head
```

### 7. Start the server

```bash
# Development (single process, both HTTP + gRPC)
python main.py

# Production (gunicorn with multiple workers, HTTP only)
gunicorn app.http.http_server:http_app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
```

> **Note:** `python main.py` starts both the HTTP server (port 8000) and gRPC server (port 50051). The gunicorn command only starts the HTTP server -- start the gRPC server separately if needed.

---

## Configuration Reference

All configuration is done via environment variables (loaded from `.env`).

### Required Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string, e.g. `postgresql://user:pass@host:5432/agl_store` |
| `JWT_SECRET_KEY` | Strong random string for signing JWT tokens. Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `FLAT_MANAGER_SECRET` | Base64-encoded secret shared with flat-manager |
| `CORS_ORIGINS` | Comma-separated allowed origins, e.g. `https://app.example.com,https://admin.example.com` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HTTP_HOST` | `0.0.0.0` | HTTP server bind address |
| `HTTP_PORT` | `8000` | HTTP server port |
| `GRPC_HOST` | `0.0.0.0` | gRPC server bind address |
| `GRPC_PORT` | `50051` | gRPC server port |
| `MAX_WORKERS` | `10` | gRPC thread pool size |
| `FLAT_MANAGER_URL` | `http://localhost:8080` | flat-manager base URL |
| `FLAT_MANAGER_API_URL` | `http://localhost:8080/api/v1` | flat-manager API URL |
| `FLAT_MANAGER_REPO` | `stable` | Default Flatpak repository |
| `FLAT_MANAGER_BRANCH` | `stable` | Default branch |
| `FLATHUB_API_URL` | `https://flathub.org/api/v2` | Flathub proxy target |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `MAX_UPLOAD_SIZE_MB` | `500` | Maximum file upload size |
| `GITHUB_CLIENT_ID` | -- | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | -- | GitHub OAuth app client secret |
| `GITLAB_CLIENT_ID` | -- | GitLab OAuth app client ID |
| `GITLAB_CLIENT_SECRET` | -- | GitLab OAuth app client secret |
| `STRIPE_PUBLISHABLE_KEY` | -- | Stripe publishable key (payments) |
| `STRIPE_SECRET_KEY` | -- | Stripe secret key (payments) |

### Docker Compose Variables

These are used by `docker-compose.yml` for the PostgreSQL container:

| Variable | Description |
|----------|-------------|
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | Database name (default: `agl_store`) |

---

## Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/) for database schema management.

```bash
# Apply all pending migrations
alembic upgrade head

# Check current migration version
alembic current

# View migration history
alembic history

# Rollback one migration
alembic downgrade -1

# Generate a new migration after model changes
alembic revision --autogenerate -m "description of changes"
```

Inside Docker:

```bash
docker compose exec backend alembic upgrade head
```

---

## Generating Tokens

Use the included script to generate flat-manager API tokens:

```bash
# Generate a publisher token
bash scripts/generate_token.sh --name my-publisher --publisher

# Generate an admin token
bash scripts/generate_token.sh --name my-admin --admin

# Generate a token with specific scopes
bash scripts/generate_token.sh --name uploader --scope upload --scope build

# See all options
bash scripts/generate_token.sh --help
```

**Available role shortcuts:**

| Flag | Scopes |
|------|--------|
| `--admin` | jobs, build, upload, publish, generate, download, republish, reviewcheck, tokenmanagement |
| `--reviewer` | reviewcheck, download, build |
| `--publisher` | build, upload, publish, download |
| `--user` | download |

---

## API Documentation

Once the server is running:

| URL | Description |
|-----|-------------|
| `/http/docs` | Swagger UI (interactive API explorer) |
| `/http/redoc` | ReDoc (alternative API docs) |
| `/http/openapi.json` | OpenAPI 3.0 schema |

### Route Structure

| Prefix | Description |
|--------|-------------|
| `/http/agl/apps` | Browse, search, and get app details |
| `/http/agl/auth` | OAuth login, user management, role changes |
| `/http/agl/flatmanager` | flat-manager proxy (builds, uploads, publishing) |
| `/http/agl/stats` | Download statistics and analytics |
| `/http/agl/favorites` | User favorite apps |
| `/http/flathub/*` | Flathub.org API proxy (appstream, search, collections, stats) |

### Authentication

The API uses JWT Bearer tokens. Include the token in the `Authorization` header:

```
Authorization: Bearer <your-token>
```

**Role hierarchy:** User < Publisher < Reviewer < Admin

| Role | Permissions |
|------|-------------|
| **User** | Browse apps, manage favorites |
| **Publisher** | Create builds, upload, publish |
| **Reviewer** | Review builds, approve/reject |
| **Admin** | All permissions, user management, token management |

---

## Deployment to Production

### Pre-deployment Checklist

- [ ] Generated strong `JWT_SECRET_KEY` (64+ characters)
- [ ] Generated strong `FLAT_MANAGER_SECRET`
- [ ] Set `POSTGRES_PASSWORD` to a strong random password
- [ ] Set `CORS_ORIGINS` to your actual frontend domain(s)
- [ ] Set `DATABASE_URL` to point to your production database
- [ ] Configured OAuth provider credentials (GitHub, GitLab, etc.)
- [ ] Run `alembic upgrade head` on the production database
- [ ] Set up a reverse proxy (nginx/Caddy) with TLS termination
- [ ] Set up database backups

### Reverse Proxy (nginx)

Place nginx in front of the backend to handle TLS and static content:

```nginx
server {
    listen 443 ssl http2;
    server_name api.your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/api.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.your-domain.com/privkey.pem;

    # HTTP API
    location /http/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;

        # File upload support
        client_max_body_size 500M;
    }

    # gRPC (if exposed externally)
    location / {
        grpc_pass grpc://127.0.0.1:50051;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name api.your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### Systemd Service (without Docker)

If deploying directly on a Linux server:

```ini
# /etc/systemd/system/agl-backend.service
[Unit]
Description=PENS AGL App Store Backend
After=network.target postgresql.service

[Service]
Type=simple
User=appuser
Group=appuser
WorkingDirectory=/opt/agl-backend
EnvironmentFile=/opt/agl-backend/.env
ExecStart=/opt/agl-backend/.venv/bin/gunicorn app.http.http_server:http_app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable agl-backend
sudo systemctl start agl-backend
sudo systemctl status agl-backend
```

### Database Backups

Set up automated PostgreSQL backups:

```bash
# Daily backup via cron (add to crontab -e)
0 2 * * * pg_dump -U youruser -h localhost agl_store | gzip > /backups/agl_store_$(date +\%Y\%m\%d).sql.gz

# Restore from backup
gunzip -c /backups/agl_store_20260326.sql.gz | psql -U youruser -h localhost agl_store
```

---

## Health Checks

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/http/health` | GET | Returns service and database status |

**Response (healthy):**

```json
{"status": "healthy", "service": "http", "database": "ok"}
```

**Response (degraded -- database unreachable):**

```json
{"status": "degraded", "service": "http", "database": "unreachable"}
```

HTTP status `200` when healthy, `503` when degraded.

---

## Troubleshooting

### Server refuses to start

```
Configuration error: JWT_SECRET_KEY is not set or uses an insecure default
Aborting startup due to missing/insecure configuration.
```

**Fix:** Set `JWT_SECRET_KEY` and `FLAT_MANAGER_SECRET` in your `.env` file to strong, unique values. See [Quick Start step 2](#2-generate-secrets).

### Database connection fails

```json
{"status": "degraded", "service": "http", "database": "unreachable"}
```

**Fix:** Verify `DATABASE_URL` in `.env` is correct and the PostgreSQL server is running:

```bash
# Docker
docker compose ps postgres

# Check connection
psql "$DATABASE_URL" -c "SELECT 1"
```

### CORS errors in browser

```
Access to fetch at '...' has been blocked by CORS policy
```

**Fix:** Add your frontend URL to `CORS_ORIGINS` in `.env`:

```env
CORS_ORIGINS=http://localhost:3000,https://your-frontend.com
```

Restart the server after changing `.env`.

### Migration errors

```bash
# Check current state
alembic current

# If the database already has tables but no migration tracking, stamp it
alembic stamp head

# Then apply future migrations normally
alembic upgrade head
```

### gRPC code not generated

```bash
bash build_proto.sh
```

Requires `grpcio-tools` to be installed (`pip install grpcio-tools`).

### Viewing logs

The server outputs structured JSON logs to stdout. In Docker:

```bash
# Follow logs
docker compose logs -f backend

# View last 100 lines
docker compose logs --tail=100 backend
```

Each request includes an `X-Request-ID` header for tracing.
