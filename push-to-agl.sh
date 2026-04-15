#!/usr/bin/env bash
# push-to-agl.sh — AGL PENS Store developer push script
# Usage:
#   ./push-to-agl.sh --token YOUR_TOKEN --app-id com.example.MyApp [options]
#
# Prerequisites:
#   - flatpak-builder installed and app built into a local repo
#   - Your AGL signing key imported: gpg --import agl-signing-key-*.gpg
#   - API key or upload token from https://admin.agl-store.cyou/developer/portal
#
# Example full flow:
#   flatpak-builder --force-clean --repo=repo build-dir com.example.MyApp.yml
#   ./push-to-agl.sh \
#       --token YOUR_UPLOAD_TOKEN \
#       --app-id com.example.MyApp \
#       --name "My App" \
#       --summary "A short description" \
#       --category Utility \
#       --repo ./repo

set -euo pipefail

API_BASE="https://admin.agl-store.cyou/api"
TOKEN=""
APP_ID=""
NAME=""
SUMMARY=""
DESCRIPTION=""
CATEGORY="Utility"
LICENSE=""
ICON=""
HOMEPAGE=""
REPO_DIR="./repo"
BUNDLE_FILE=""
KEEP_BUNDLE=false
GPG_KEY=""  # fingerprint of the AGL signing key (auto-detected if omitted)
ARCH=""     # target architecture (default: native; set to aarch64 for Pi 4)

# ── Parse arguments ─────────────────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Required:
  --token TOKEN         Upload token or API key from the developer portal
  --app-id ID           Flatpak app ID (e.g. com.example.MyApp)
  --name NAME           Display name of the app
  --summary TEXT        One-line description (shown in store listing)

Optional:
  --description TEXT    Full description (default: same as summary)
  --category CAT        App category (default: Utility)
  --license SPDX        License identifier (e.g. MIT, GPL-3.0)
  --icon URL            URL to app icon (PNG, 128x128 recommended)
  --homepage URL        Project homepage URL
  --repo DIR            Path to local flatpak repo (default: ./repo)
  --bundle FILE         Use existing .flatpak bundle instead of building from repo
  --gpg-key FINGERPRINT GPG key fingerprint to sign with (auto-detected if omitted)
  --arch ARCH           Target architecture: x86_64 (default) or aarch64
  --keep-bundle         Do not delete the .flatpak bundle after upload

First-time setup:
  1. Log in to https://admin.agl-store.cyou/developer/portal
  2. Download your signing key (Signing Key section → Download)
  3. Import it: gpg --import agl-signing-key-*.gpg
  4. Run this script — it will sign your bundle automatically

Example:
  flatpak-builder --force-clean --repo=repo build-dir com.example.MyApp.yml
  $(basename "$0") \\
    --token YOUR_UPLOAD_TOKEN \\
    --app-id com.example.MyApp \\
    --name "My App" \\
    --summary "Does something useful" \\
    --category Utility \\
    --repo ./repo
EOF
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --token)       TOKEN="$2"; shift 2 ;;
    --app-id)      APP_ID="$2"; shift 2 ;;
    --name)        NAME="$2"; shift 2 ;;
    --summary)     SUMMARY="$2"; shift 2 ;;
    --description) DESCRIPTION="$2"; shift 2 ;;
    --category)    CATEGORY="$2"; shift 2 ;;
    --license)     LICENSE="$2"; shift 2 ;;
    --icon)        ICON="$2"; shift 2 ;;
    --homepage)    HOMEPAGE="$2"; shift 2 ;;
    --repo)        REPO_DIR="$2"; shift 2 ;;
    --bundle)      BUNDLE_FILE="$2"; shift 2 ;;
    --arch)        ARCH="$2"; shift 2 ;;
    --gpg-key)     GPG_KEY="$2"; shift 2 ;;
    --keep-bundle) KEEP_BUNDLE=true; shift ;;
    -h|--help)     usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

# ── Validate required args ────────────────────────────────────────────────────
[[ -z "$TOKEN" ]]   && { echo "Error: --token is required"; usage; }
[[ -z "$APP_ID" ]]  && { echo "Error: --app-id is required"; usage; }
[[ -z "$NAME" ]]    && { echo "Error: --name is required"; usage; }
[[ -z "$SUMMARY" ]] && { echo "Error: --summary is required"; usage; }

# Validate app_id: no segment may start with a digit
IFS='.' read -ra SEGS <<< "$APP_ID"
if [[ ${#SEGS[@]} -lt 3 ]]; then
  echo "Error: app_id must have at least 3 segments (e.g. com.example.MyApp)"
  exit 1
fi
for seg in "${SEGS[@]}"; do
  if [[ "$seg" =~ ^[0-9] ]]; then
    echo "Error: app_id segment '$seg' starts with a digit."
    echo "  Flatpak rejects such IDs. Rename it, e.g. '2048' → 'Game2048'"
    exit 1
  fi
done

[[ -z "$DESCRIPTION" ]] && DESCRIPTION="$SUMMARY"

# ── Prerequisite: gpg must be available ──────────────────────────────────────
if ! command -v gpg &>/dev/null; then
  echo "Error: gpg not found. Install GnuPG (e.g. sudo apt install gnupg)"
  exit 1
fi

# ── Auto-detect AGL signing key if not specified ─────────────────────────────
if [[ -z "$GPG_KEY" ]]; then
  GPG_KEY=$(gpg --list-secret-keys --with-colons 2>/dev/null \
    | awk -F: '/^uid:/ && /AGL Developer/' \
    | head -1 | cut -d: -f10 || true)
  if [[ -z "$GPG_KEY" ]]; then
    # fallback: try fingerprint from uid field
    GPG_KEY=$(gpg --list-secret-keys --with-colons 2>/dev/null \
      | awk -F: 'prev=="fpr" && /AGL Developer/{print $10} {prev=$1}' \
      | head -1 || true)
    # Simpler fallback
    GPG_KEY=$(gpg --list-secret-keys --with-colons 2>/dev/null \
      | grep -A1 'AGL Developer' | grep '^fpr' | head -1 | cut -d: -f10 || true)
  fi
  if [[ -z "$GPG_KEY" ]]; then
    echo ""
    echo "Error: AGL signing key not found in your GPG keyring."
    echo ""
    echo "  1. Log in to https://admin.agl-store.cyou/developer/portal"
    echo "  2. Go to the 'Signing Key' section and click 'Download Signing Key'"
    echo "  3. Import it:  gpg --import agl-signing-key-*.gpg"
    echo "  4. Verify:     gpg --list-secret-keys | grep 'AGL Developer'"
    echo ""
    echo "  Or specify the key explicitly: --gpg-key YOUR_FINGERPRINT"
    exit 1
  fi
  echo "==> Using AGL signing key: ${GPG_KEY: -16}"
fi

# ── Step 1: Build bundle ──────────────────────────────────────────────────────
CLEANUP_BUNDLE=false
if [[ -z "$BUNDLE_FILE" ]]; then
  if [[ ! -d "$REPO_DIR" ]]; then
    echo "Error: repo directory '$REPO_DIR' not found."
    echo "  Build it first: flatpak-builder --force-clean --repo=repo build-dir YOUR_MANIFEST.yml"
    exit 1
  fi
  BUNDLE_FILE="${APP_ID}.flatpak"
  echo "==> Building bundle from $REPO_DIR..."
  ARCH_ARGS=()
  [[ -n "$ARCH" ]] && ARCH_ARGS=(--arch "$ARCH")
  flatpak build-bundle "${ARCH_ARGS[@]}" "$REPO_DIR" "$BUNDLE_FILE" "$APP_ID"
  echo "    Bundle: $BUNDLE_FILE ($(du -sh "$BUNDLE_FILE" | cut -f1))"
  $KEEP_BUNDLE || CLEANUP_BUNDLE=true
fi

SIG_FILE="${BUNDLE_FILE}.asc"

cleanup() {
  $CLEANUP_BUNDLE && [[ -f "$BUNDLE_FILE" ]] && rm -f "$BUNDLE_FILE"
  [[ -f "$SIG_FILE" ]] && rm -f "$SIG_FILE"
}
trap cleanup EXIT

# ── Step 2: Sign bundle ───────────────────────────────────────────────────────
echo "==> Signing bundle with key ${GPG_KEY: -16}..."
rm -f "$SIG_FILE"
gpg --armor --detach-sign \
    --default-key "$GPG_KEY" \
    --output "$SIG_FILE" \
    "$BUNDLE_FILE"
echo "    Signature: $SIG_FILE"

# ── Step 3: Upload signed bundle ──────────────────────────────────────────────
echo "==> Uploading bundle to AGL store..."
UPLOAD_RESP=$(curl -sf \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@${BUNDLE_FILE};type=application/octet-stream" \
  -F "signature=$(cat "$SIG_FILE")" \
  "${API_BASE}/developer/upload-bundle") || {
    echo "Error: Upload failed."
    echo "  Check your token, signing key, and network connection."
    echo "  Bundle file:  $BUNDLE_FILE"
    echo "  Signature:    $SIG_FILE"
    exit 1
}

DETECTED_ID=$(echo "$UPLOAD_RESP" | grep -o '"app_id":"[^"]*"' | cut -d'"' -f4 || true)
echo "    Upload successful. Detected app_id: ${DETECTED_ID:-$APP_ID}"

# ── Step 4: Submit metadata ───────────────────────────────────────────────────
echo "==> Submitting app metadata..."

JSON_PARTS="{\"app_id\": \"$APP_ID\", \"name\": \"$NAME\", \"summary\": \"$SUMMARY\", \"description\": \"$DESCRIPTION\", \"app_type\": \"desktop-application\", \"categories\": [\"$CATEGORY\"]"
[[ -n "$LICENSE" ]]  && JSON_PARTS="$JSON_PARTS, \"license\": \"$LICENSE\""
[[ -n "$ICON" ]]     && JSON_PARTS="$JSON_PARTS, \"icon\": \"$ICON\""
[[ -n "$HOMEPAGE" ]] && JSON_PARTS="$JSON_PARTS, \"homepage\": \"$HOMEPAGE\""
JSON_PARTS="$JSON_PARTS}"

SUBMIT_RESP=$(curl -sf \
  -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$JSON_PARTS" \
  "${API_BASE}/developer/submit") || {
    echo "Error: Metadata submission failed."
    exit 1
}

SUB_ID=$(echo "$SUBMIT_RESP" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2 || true)

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "✓ Done! Submission #${SUB_ID:-?} queued for review."
echo ""
echo "  App ID:    $APP_ID"
echo "  Track:     https://admin.agl-store.cyou/developer/portal"
echo "  An admin will review and scan your app."
echo "  You'll receive an email when it goes live."
