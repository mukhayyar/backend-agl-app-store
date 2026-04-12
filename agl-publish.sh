#!/usr/bin/env bash
# agl-publish.sh — Build and publish a Flatpak app to the AGL Store
# Usage: ./agl-publish.sh <manifest.yml> <api_key>
# Example: ./agl-publish.sh com.pens.MyApp.yml YOUR_API_KEY
#          AGL_API_KEY=YOUR_KEY ./agl-publish.sh com.pens.MyApp.yml

set -euo pipefail

MANIFEST=${1:-}
API_KEY=${2:-${AGL_API_KEY:-}}
API_BASE="https://admin.agl-store.cyou/api/v1"
CHANNEL="stable"

if [[ -z "$MANIFEST" || -z "$API_KEY" ]]; then
  echo "Usage: agl-publish.sh <manifest.yml> <api_key>"
  echo "       API key can also be set via AGL_API_KEY env var"
  exit 1
fi

APP_ID=$(grep "^app-id:" "$MANIFEST" | awk "{print \$2}")
if [[ -z "$APP_ID" ]]; then
  echo "ERROR: Could not parse app-id from manifest" >&2
  exit 1
fi

echo ""
echo "============================================"
echo " AGL Store Publisher"
echo " App: $APP_ID"
echo "============================================"
echo ""

# Step 1: Build
echo "[1/4] Building $APP_ID..."
flatpak-builder --user --force-clean build-dir "$MANIFEST"
echo "      Build OK"

# Step 2: Export (CRITICAL — never skip this)
echo "[2/4] Exporting to local repo..."
echo "      NOTE: flatpak build-export is required for correct xa.metadata."
echo "      Skipping this causes: \"Commit metadata not matching expected metadata\""
flatpak build-export repo build-dir
echo "      Export OK"

# Step 3: Push to store
echo "[3/4] Pushing to AGL Store..."
if ! command -v flat-manager-client &>/dev/null; then
  pip install -q flat-manager-client
fi
flat-manager-client push \
  --token "$API_KEY" \
  "$API_BASE" \
  "$CHANNEL" \
  repo/

# Step 4: Done
echo ""
echo "[4/4] Done!"
echo ""
echo "  App published: $APP_ID"
echo "  Channel: $CHANNEL"
echo ""
echo "  Verify installation:"
echo "    flatpak remote-add --if-not-exists penshub https://repo.agl-store.cyou/repo --gpg-import=<(curl -s https://repo.agl-store.cyou/public.gpg)"
echo "    flatpak update --appstream penshub"
echo "    flatpak install penshub $APP_ID"
