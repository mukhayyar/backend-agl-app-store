#!/bin/sh
set -e

REPO_PATH="${FLATPAK_REPO_PATH:-/srv/flatpak-repo}"

# Initialise OSTree repo on first run
if [ ! -f "$REPO_PATH/config" ]; then
    echo "[flat-manager] Initialising OSTree archive-z2 repo at $REPO_PATH..."
    ostree --repo="$REPO_PATH" init --mode=archive-z2
    echo "[flat-manager] Repo initialised."
fi

exec "$@"
