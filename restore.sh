#!/usr/bin/env bash
# AGL App Store — Restore script
# Restores from a backup created by backup.sh
# Usage: ./restore.sh agl-backup-YYYYMMDD-HHMMSS.tar.gz
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BACKUP_ARCHIVE="${1:-}"
if [ -z "$BACKUP_ARCHIVE" ] || [ ! -f "$BACKUP_ARCHIVE" ]; then
  echo "Usage: ./restore.sh <backup-archive.tar.gz>"
  echo "Create a backup first with:  ./backup.sh"
  exit 1
fi

echo "=== AGL App Store Restore ==="
echo "Archive: $BACKUP_ARCHIVE"
echo ""
read -rp "This will OVERWRITE the current database and repo. Continue? [y/N] " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

# ── Extract backup ────────────────────────────────────────────────────────
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
echo "[0/6] Extracting archive..."
tar -xzf "$BACKUP_ARCHIVE" -C "$TMPDIR"
BACKUP_DIR="$(ls -d "$TMPDIR"/agl-backup-*)"
echo "      OK"

# ── Load env ──────────────────────────────────────────────────────────────
if [ -f "$BACKUP_DIR/.env.backup" ] && [ ! -f .env ]; then
  echo "[!] No .env found — copying from backup"
  cp "$BACKUP_DIR/.env.backup" .env
fi
set -a; source .env; set +a
DB_USER="${DB_USER:-pensagl}"
REPO_PATH="${FLATPAK_REPO_PATH:-/srv/flatpak-repo}"

# ── 1. TLS certs ──────────────────────────────────────────────────────────
echo "[1/6] Restoring TLS certificates..."
if [ -d "$BACKUP_DIR/certs" ]; then
  mkdir -p certs
  cp -r "$BACKUP_DIR/certs/." certs/
  echo "      OK"
else
  echo "      Not in backup — add certs manually before running deploy.sh"
fi

# ── 2. GPG keys ───────────────────────────────────────────────────────────
echo "[2/6] Importing GPG keys..."
if [ -f "$BACKUP_DIR/gpg-secret-keys.asc" ]; then
  gpg --import "$BACKUP_DIR/gpg-secret-keys.asc" 2>&1 | tail -3
  echo "      OK"
fi

# ── 3. OSTree repo ────────────────────────────────────────────────────────
echo "[3/6] Restoring OSTree repo to $REPO_PATH..."
mkdir -p "$REPO_PATH"
rsync -a --delete "$BACKUP_DIR/flatpak-repo/" "$REPO_PATH/"
echo "      Rebuilding deltas (this may take a few minutes)..."
flatpak build-update-repo --generate-static-deltas "$REPO_PATH" || true
echo "      OK"

# ── 4. Start postgres ─────────────────────────────────────────────────────
echo "[4/6] Starting PostgreSQL..."
docker compose up -d postgres
echo "      Waiting for postgres to be ready..."
until docker compose exec -T postgres pg_isready -U "$DB_USER" &>/dev/null; do
  sleep 2
done
echo "      OK"

# ── 5. Restore databases ──────────────────────────────────────────────────
echo "[5/6] Restoring databases..."
if [ -f "$BACKUP_DIR/agl_store.sql" ]; then
  docker compose exec -T postgres psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS agl_store;" postgres 2>/dev/null || true
  docker compose exec -T postgres psql -U "$DB_USER" -c "CREATE DATABASE agl_store;" postgres
  docker compose exec -T postgres psql -U "$DB_USER" agl_store < "$BACKUP_DIR/agl_store.sql"
  echo "      agl_store: OK"
fi
if [ -f "$BACKUP_DIR/flatpak_repo.sql" ]; then
  docker compose exec -T postgres psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS flatpak_repo;" postgres 2>/dev/null || true
  docker compose exec -T postgres psql -U "$DB_USER" -c "CREATE DATABASE flatpak_repo;" postgres
  docker compose exec -T postgres psql -U "$DB_USER" flatpak_repo < "$BACKUP_DIR/flatpak_repo.sql"
  echo "      flatpak_repo: OK"
fi

# ── 6. Run setup + deploy ─────────────────────────────────────────────────
echo "[6/6] Running setup and deploy..."
./setup.sh
./deploy.sh

echo ""
echo "=== Restore complete! ==="
echo "All services should now be running. Check with: docker compose ps"
