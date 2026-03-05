#!/usr/bin/env bash
# build_scripts/create_dmg.sh
#
# Packages the macOS .app bundle into a distributable .dmg.
#
# Prerequisites:
#   brew install create-dmg
#
# Usage (from project root, after pyinstaller main.spec):
#   bash build_scripts/create_dmg.sh [version]
#
# Output: dist/NX-Librarian-<version>.dmg

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
APP="$DIST/NX-Librarian.app"
VERSION="${1:-3.0.0}"
DMG_OUT="$DIST/NX-Librarian-${VERSION}.dmg"

if [ ! -d "$APP" ]; then
    echo "ERROR: .app bundle not found at $APP — run pyinstaller main.spec first."
    exit 1
fi

if ! command -v create-dmg &>/dev/null; then
    echo "create-dmg not found. Installing via Homebrew …"
    brew install create-dmg
fi

# Remove any previous attempt
rm -f "$DMG_OUT"

create-dmg \
    --volname "NX-Librarian ${VERSION}" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 128 \
    --icon "NX-Librarian.app" 170 180 \
    --hide-extension "NX-Librarian.app" \
    --app-drop-link 430 180 \
    --no-internet-enable \
    "$DMG_OUT" \
    "$APP"

echo "Done: $DMG_OUT"
