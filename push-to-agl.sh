#!/usr/bin/env bash
# push-to-agl.sh — AGL PENS Store developer push script
# Usage:
#   ./push-to-agl.sh --token YOUR_API_KEY --app-id com.example.MyApp [options]
#
# Prerequisites:
#   - flatpak-builder installed and app built into a local repo
#   - API key from https://admin.agl-store.cyou/developer/portal
#
# Example full flow:
#   flatpak-builder --force-clean --repo=repo build-dir com.example.MyApp.yml
#   ./push-to-agl.sh \
#       --token sk-xxxx \
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

# ── Parse arguments ────────────────────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Required:
  --token TOKEN         API key from the developer portal
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
  --keep-bundle         Do not delete the .flatpak bundle after upload

Example:
  flatpak-builder --force-clean --repo=repo build-dir com.example.MyApp.yml
  $(basename "$0") \\
    --token sk-xxxx \\
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
    --keep-bundle) KEEP_BUNDLE=true; shift ;;
    -h|--help)     usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

# ── Validate required args ─────────────────────────────────────────────────────
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
    echo "  Flatpak will reject this ID at install time."
    echo "  Rename it, e.g. '2048' → 'Game2048'"
    exit 1
  fi
done

[[ -z "$DESCRIPTION" ]] && DESCRIPTION="$SUMMARY"

# ── Step 1: Build bundle ───────────────────────────────────────────────────────
CLEANUP_BUNDLE=false
if [[ -z "$BUNDLE_FILE" ]]; then
  if [[ ! -d "$REPO_DIR" ]]; then
    echo "Error: repo directory '$REPO_DIR' not found."
    echo "  Build it first: flatpak-builder --force-clean --repo=repo build-dir YOUR_MANIFEST.yml"
    exit 1
  fi

  BUNDLE_FILE="${APP_ID}.flatpak"
  echo "==> Building bundle from $REPO_DIR..."
  flatpak build-bundle "$REPO_DIR" "$BUNDLE_FILE" "$APP_ID"
  echo "    Bundle: $BUNDLE_FILE ($(du -sh "$BUNDLE_FILE" | cut -f1))"
  $KEEP_BUNDLE || CLEANUP_BUNDLE=true
fi

cleanup() {
  if $CLEANUP_BUNDLE && [[ -f "$BUNDLE_FILE" ]]; then
    rm -f "$BUNDLE_FILE"
  fi
}
trap cleanup EXIT

# ── Step 2: Upload bundle ──────────────────────────────────────────────────────
echo "==> Uploading bundle to AGL store..."
UPLOAD_RESP=$(curl -sf \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@${BUNDLE_FILE};type=application/octet-stream" \
  "${API_BASE}/developer/upload-bundle") || {
    echo "Error: Upload failed. Check your API key and network connection."
    exit 1
}

DETECTED_ID=$(echo "$UPLOAD_RESP" | grep -o '"app_id":"[^"]*"' | cut -d'"' -f4 || true)
echo "    Upload successful. Detected app_id: ${DETECTED_ID:-$APP_ID}"

# ── Step 3: Submit metadata ────────────────────────────────────────────────────
echo "==> Submitting app metadata..."

# Build JSON
JSON=$(cat <<ENDJSON
{
  "app_id": "$APP_ID",
  "name": "$NAME",
  "summary": "$SUMMARY",
  "description": "$DESCRIPTION",
  "app_type": "desktop-application",
  "categories": ["$CATEGORY"]
  $([ -n "$LICENSE" ]  && echo ", \"license\": \"$LICENSE\"")
  $([ -n "$ICON" ]     && echo ", \"icon\": \"$ICON\"")
  $([ -n "$HOMEPAGE" ] && echo ", \"homepage\": \"$HOMEPAGE\"")
}
ENDJSON
)

SUBMIT_RESP=$(curl -sf \
  -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$JSON" \
  "${API_BASE}/developer/submit") || {
    echo "Error: Submission failed."
    echo "Response: $SUBMIT_RESP"
    exit 1
}

SUB_ID=$(echo "$SUBMIT_RESP" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2 || true)

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "✓ Done! Submission #${SUB_ID:-?} is now in the admin review queue."
echo ""
echo "  Track status: https://admin.agl-store.cyou/developer/portal"
echo "  App ID:       $APP_ID"
echo "  Next steps:   An admin will review, scan, and approve your app."
echo "                You'll receive an email when it goes live."
