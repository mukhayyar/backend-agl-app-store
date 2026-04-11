#!/usr/bin/env bash
# AGL App Store — Backup script
# Creates a portable backup archive for server migration
# Usage: ./backup.sh [output-dir]
# Output: agl-backup-YYYYMMDD-HHMMSS.tar.gz
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
OUTPUT_DIR="${1:-.}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_NAME="agl-backup-$TIMESTAMP"
BACKUP_DIR="$OUTPUT_DIR/$BACKUP_NAME"

echo "=== AGL App Store Backup ==="
echo "Output: $BACKUP_DIR.tar.gz"
echo ""

set -a; [ -f .env ] && source .env; set +a
DB_USER="${DB_USER:-pensagl}"
DB_PASSWORD="${DB_PASSWORD:-}"
REPO_PATH="${FLATPAK_REPO_PATH:-/srv/flatpak-repo}"

mkdir -p "$BACKUP_DIR"

# ── 1. Database dumps ─────────────────────────────────────────────────────
echo "[1/5] Dumping PostgreSQL databases..."
docker compose exec -T postgres pg_dump -U "$DB_USER" agl_store \
  > "$BACKUP_DIR/agl_store.sql"
docker compose exec -T postgres pg_dump -U "$DB_USER" flatpak_repo \
  > "$BACKUP_DIR/flatpak_repo.sql" 2>/dev/null || \
  echo "      flatpak_repo DB not found — skipping"
echo "      OK"

# ── 2. OSTree repo ────────────────────────────────────────────────────────
echo "[2/5] Archiving OSTree repo (objects + refs, no deltas)..."
mkdir -p "$BACKUP_DIR/flatpak-repo"
# Copy only essential parts (deltas can be regenerated)
rsync -a --exclude='deltas/' --exclude='delta-indexes/' --exclude='tmp/' \
  "$REPO_PATH/" "$BACKUP_DIR/flatpak-repo/"
echo "      OK ($(du -sh "$BACKUP_DIR/flatpak-repo" | cut -f1))"

# ── 3. GPG keys ───────────────────────────────────────────────────────────
echo "[3/5] Exporting GPG keys..."
gpg --armor --export-secret-keys > "$BACKUP_DIR/gpg-secret-keys.asc" 2>/dev/null || true
gpg --armor --export            > "$BACKUP_DIR/gpg-public-keys.asc"  2>/dev/null || true
echo "      OK"

# ── 4. TLS certs ──────────────────────────────────────────────────────────
echo "[4/5] Copying TLS certificates..."
if [ -d certs ] && [ "$(ls -A certs 2>/dev/null)" ]; then
  cp -r certs "$BACKUP_DIR/certs"
  echo "      OK"
else
  echo "      No certs directory found — skipping"
fi

# ── 5. Config snapshot ────────────────────────────────────────────────────
echo "[5/5] Saving config snapshot..."
cp .env "$BACKUP_DIR/.env.backup"
cp docker/flat-manager/config.json "$BACKUP_DIR/flat-manager-config.json" 2>/dev/null || true
echo "      OK"

# ── Archive ───────────────────────────────────────────────────────────────
echo ""
echo "Creating archive..."
tar -czf "$OUTPUT_DIR/$BACKUP_NAME.tar.gz" -C "$OUTPUT_DIR" "$BACKUP_NAME"
rm -rf "$BACKUP_DIR"

SIZE="$(du -sh "$OUTPUT_DIR/$BACKUP_NAME.tar.gz" | cut -f1)"
echo ""
echo "=== Backup complete ==="
echo "File: $OUTPUT_DIR/$BACKUP_NAME.tar.gz ($SIZE)"
echo ""
echo "To restore on a new server:"
echo "  1. Clone the repo: git clone <repo-url> && cd agl"
echo "  2. Copy backup: scp $BACKUP_NAME.tar.gz newserver:/root/agl/"
echo "  3. Run: ./restore.sh $BACKUP_NAME.tar.gz"
