#!/usr/bin/env bash
# AGL App Store — One-Command Deployment
# Usage: git clone <repo> && cd agl && cp .env.example .env && vim .env && ./deploy.sh
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
error() { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 1. Pre-flight checks ──────────────────────────────────────────────────────
info "Running pre-flight checks..."
[ -f .env ] || error ".env not found — copy .env.example to .env and fill in values"
command -v docker >/dev/null 2>&1 || error "docker is not installed"
docker compose version >/dev/null 2>&1 || error "docker compose plugin is not installed"
command -v envsubst >/dev/null 2>&1 || error "envsubst not found — install gettext"

set -a; source .env; set +a

[ -n "${DOMAIN:-}" ]              || error "DOMAIN is not set in .env"
[ -n "${DB_PASSWORD:-}" ]         || error "DB_PASSWORD is not set in .env"
[ -n "${FLAT_MANAGER_SECRET:-}" ] || error "FLAT_MANAGER_SECRET is not set in .env"
[ -n "${API_SECRET:-}" ]          || error "API_SECRET is not set in .env"
[ -n "${GPG_KEY_ID:-}" ]          || warn  "GPG_KEY_ID is not set — flat-manager signing will not work"

# ── 2. TLS certificates ───────────────────────────────────────────────────────
info "Checking TLS certificates..."
mkdir -p certs
if [ ! -f certs/cf_origin.crt ] || [ ! -f certs/cf_origin.key ]; then
    warn "Cloudflare origin certificates not found in ./certs/"
    warn "Place cf_origin.crt and cf_origin.key in ./certs/ before starting Caddy."
    warn "Alternatively, remove 'import cf_tls' from Caddyfile and use auto-ACME."
fi

# ── 3. Render Caddyfile from template ─────────────────────────────────────────
info "Rendering Caddyfile from template..."
envsubst < Caddyfile.template > Caddyfile
info "Caddyfile written for domain: $DOMAIN"

# ── 4. flat-manager config ────────────────────────────────────────────────────
info "Rendering flat-manager config..."
envsubst < docker/flat-manager/config.json.template > docker/flat-manager/config.json
info "flat-manager config.json written"

# ── 5. Ensure flat-manager binary is available ────────────────────────────────
info "Checking flat-manager binary..."
FLATMGR_BIN="docker/flat-manager/flat-manager"
if [ ! -f "$FLATMGR_BIN" ]; then
    if command -v flat-manager >/dev/null 2>&1; then
        info "Copying flat-manager binary from system path..."
        cp "$(command -v flat-manager)" "$FLATMGR_BIN"
    else
        error "flat-manager binary not found.\n" \
              "  Option A: Install flat-manager and run this script again.\n" \
              "  Option B: Place the x86_64-Linux binary at $FLATMGR_BIN"
    fi
fi

# Copy gentoken and flat-manager-client to docker context
if [ -f /usr/local/bin/gentoken ] && [ ! -f docker/flat-manager/gentoken ]; then
  cp /usr/local/bin/gentoken docker/flat-manager/gentoken
fi
FLAT_CLI_REAL="$(readlink -f /usr/local/bin/flat-manager-client 2>/dev/null || echo /usr/local/bin/flat-manager-client)"
if [ -f "$FLAT_CLI_REAL" ] && [ ! -f docker/flat-manager/flat-manager-client ]; then
  cp "$FLAT_CLI_REAL" docker/flat-manager/flat-manager-client
fi

# ── 6. GPG keyring ────────────────────────────────────────────────────────────
info "Checking GPG keyring..."
GNUPG_VOL="$(docker volume ls -q | grep -E '^(agl_)?gnupg_data$' | head -1)"
if [ -z "$GNUPG_VOL" ]; then
    warn "gnupg_data volume does not exist yet — it will be created on first run."
    warn "After deploy, import your GPG key:"
    warn "  docker compose exec flat-manager gpg --import /path/to/secret.gpg"
fi

# ── 7. Build images ───────────────────────────────────────────────────────────
info "Building Docker images (this may take a few minutes on first run)..."
docker compose build --parallel

# ── 8. Start services ─────────────────────────────────────────────────────────
info "Starting all services..."
docker compose up -d

# ── 9. Wait for health ────────────────────────────────────────────────────────
info "Waiting for backend to be healthy..."
for i in $(seq 1 30); do
    if docker compose exec -T rest curl -sf http://localhost:8002/health >/dev/null 2>&1; then
        info "REST API is healthy ✓"
        break
    fi
    sleep 2
    [ "$i" -lt 30 ] || warn "REST API health check timed out — check logs: docker compose logs rest"
done

# ── 10. Summary ───────────────────────────────────────────────────────────────
echo ""
info "==========================================="
info "  AGL App Store deployed successfully!"
info "==========================================="
info "  Store:   https://${DOMAIN}"
info "  Admin:   https://admin.${DOMAIN}"
info "  Hub:     https://hub.${DOMAIN}"
info "  Repo:    https://repo.${DOMAIN}"
info "  API:     https://api.${DOMAIN}"
info ""
info "Useful commands:"
info "  docker compose logs -f          # tail all logs"
info "  docker compose logs -f rest     # tail REST API logs"
info "  docker compose ps               # service status"
info "  docker compose restart rest     # restart a service"
