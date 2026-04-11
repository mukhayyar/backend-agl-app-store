#!/usr/bin/env bash
# AGL App Store — First-time setup script
# Run this ONCE on a fresh server before ./deploy.sh
# Usage: ./setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== AGL App Store Setup ==="
echo ""

# ── 1. Load .env ──────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  echo "[!] .env not found. Copying from .env.example..."
  cp .env.example .env
  echo "    Edit .env with your values, then re-run this script."
  exit 1
fi
set -a; source .env; set +a

# ── 2. Check Docker ───────────────────────────────────────────────────────
echo "[1/8] Checking Docker..."
docker info &>/dev/null || { echo "ERROR: Docker not running"; exit 1; }
docker compose version &>/dev/null || { echo "ERROR: docker compose not found"; exit 1; }
echo "      OK"

# ── 3. Prepare flatpak repo directory ────────────────────────────────────
REPO_PATH="${FLATPAK_REPO_PATH:-/srv/flatpak-repo}"
echo "[2/8] Preparing OSTree repo at $REPO_PATH..."
mkdir -p "$REPO_PATH"
if [ ! -f "$REPO_PATH/config" ]; then
  ostree init --mode=archive-z2 --repo="$REPO_PATH"
  echo "      Initialized new OSTree repo"
else
  echo "      Existing repo found — skipping init"
fi

# ── 4. Copy flat-manager binaries to docker context ──────────────────────
echo "[3/8] Copying flat-manager binaries..."
FLAT_MGR_SRC="/usr/local/bin/flat-manager"
GENTOKEN_SRC="/usr/local/bin/gentoken"
FLAT_CLI_SRC="/usr/local/bin/flat-manager-client"

for bin in "$FLAT_MGR_SRC" "$GENTOKEN_SRC"; do
  if [ ! -f "$bin" ]; then
    echo "ERROR: $bin not found. Install flat-manager first."
    echo "  See: https://github.com/flatpak/flat-manager"
    exit 1
  fi
done
cp "$FLAT_MGR_SRC" docker/flat-manager/flat-manager
cp "$GENTOKEN_SRC" docker/flat-manager/gentoken

# flat-manager-client may be a symlink to source — copy the real binary
if [ -L "$FLAT_CLI_SRC" ]; then
  REAL_CLI="$(readlink -f "$FLAT_CLI_SRC")"
else
  REAL_CLI="$FLAT_CLI_SRC"
fi
if [ -f "$REAL_CLI" ]; then
  cp "$REAL_CLI" docker/flat-manager/flat-manager-client
else
  echo "WARNING: flat-manager-client not found at $FLAT_CLI_SRC — build from source if needed"
fi
echo "      OK"

# ── 5. GPG key setup ─────────────────────────────────────────────────────
echo "[4/8] Setting up GPG signing key..."
if ! gpg --list-keys "$ADMIN_EMAIL" &>/dev/null; then
  echo "      Generating RSA-4096 GPG key for $ADMIN_EMAIL..."
  gpg --batch --gen-key <<EOF
Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: AGL Store
Name-Email: ${ADMIN_EMAIL}
Expire-Date: 5y
%no-passphrase
%commit
EOF
fi
GPG_KEY_ID="$(gpg --with-colons --list-keys "$ADMIN_EMAIL" | awk -F: '/^fpr/{print $10; exit}')"
echo "      GPG key: $GPG_KEY_ID"

# Export public key to repo
gpg --armor --export "$ADMIN_EMAIL" > "$REPO_PATH/public.gpg"

# Update .env and config template with key ID
sed -i "s/^GPG_KEY_ID=.*/GPG_KEY_ID=$GPG_KEY_ID/" .env

# ── 6. Render flat-manager config.json ───────────────────────────────────
echo "[5/8] Rendering flat-manager config.json..."
FLAT_MANAGER_SECRET_B64="${FLAT_MANAGER_SECRET_B64:-$(openssl rand -base64 32)}"
FLATPAK_REPO_NAME="${FLATPAK_REPO_NAME:-agl-store}"
export GPG_KEY_ID FLAT_MANAGER_SECRET_B64 FLATPAK_REPO_NAME DB_USER DB_PASSWORD
envsubst < docker/flat-manager/config.json.template > docker/flat-manager/config.json
echo "      Written docker/flat-manager/config.json"

# ── 7. Render Caddyfile ───────────────────────────────────────────────────
echo "[6/8] Rendering Caddyfile..."
export DOMAIN
envsubst < Caddyfile.template > Caddyfile
echo "      Written Caddyfile"

# ── 8. Check TLS certs ────────────────────────────────────────────────────
echo "[7/8] Checking TLS certificates..."
mkdir -p certs
if [ ! -f certs/cf_origin.crt ] || [ ! -f certs/cf_origin.key ]; then
  echo ""
  echo "  ⚠️  Cloudflare Origin Certificates not found in ./certs/"
  echo "  Generate them at: Cloudflare Dashboard → SSL/TLS → Origin Server"
  echo "  Save as:  certs/cf_origin.crt  and  certs/cf_origin.key"
  echo ""
  echo "  Alternatively for self-signed (dev only):"
  echo "    openssl req -x509 -newkey rsa:4096 -keyout certs/cf_origin.key \\"
  echo "      -out certs/cf_origin.crt -days 365 -nodes \\"
  echo "      -subj '/CN=${DOMAIN:-localhost}'"
  echo ""
fi

# ── 9. Generate admin JWT token ───────────────────────────────────────────
echo "[8/8] Generating flat-manager admin token..."
if command -v gentoken &>/dev/null; then
  ADMIN_TOKEN="$(gentoken --secret "$FLAT_MANAGER_SECRET" --name "agl-backend" \
    --repo stable --scope build --scope upload --scope publish --prefix '*' 2>/dev/null || true)"
  if [ -n "$ADMIN_TOKEN" ]; then
    sed -i "s/^FLAT_MANAGER_ADMIN_TOKEN=.*/FLAT_MANAGER_ADMIN_TOKEN=$ADMIN_TOKEN/" .env
    echo "      Admin token written to .env"
  fi
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Verify .env (especially DOMAIN, DB_PASSWORD, API_SECRET, JWT_SECRET_KEY)"
echo "  2. Add TLS certs to ./certs/ if not already done"
echo "  3. Run:  ./deploy.sh"
echo ""
