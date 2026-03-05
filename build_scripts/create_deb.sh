#!/usr/bin/env bash
# build_scripts/create_deb.sh
#
# Builds a Debian/Ubuntu .deb package from the PyInstaller one-file binary.
#
# Usage (from project root):
#   bash build_scripts/create_deb.sh [version]
#
# Output: dist/nxlibrarian_<version>_amd64.deb

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
BINARY="$DIST/NX-Librarian"
VERSION="${1:-3.0.0}"
PKG_DIR="$DIST/deb_pkg"
DEB_OUT="$DIST/nxlibrarian_${VERSION}_amd64.deb"

if [ ! -f "$BINARY" ]; then
    echo "ERROR: Binary not found at $BINARY — run pyinstaller main.spec first."
    exit 1
fi

# ── Assemble package tree ─────────────────────────────────────────────────────
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$PKG_DIR/usr/share/pixmaps"

cp "$BINARY" "$PKG_DIR/usr/bin/nxlibrarian"
chmod 755 "$PKG_DIR/usr/bin/nxlibrarian"

cp "$ROOT/logo.png" "$PKG_DIR/usr/share/icons/hicolor/256x256/apps/nxlibrarian.png"
cp "$ROOT/logo.png" "$PKG_DIR/usr/share/pixmaps/nxlibrarian.png"

cat > "$PKG_DIR/usr/share/applications/nxlibrarian.desktop" <<EOF
[Desktop Entry]
Name=NX-Librarian
GenericName=Switch Archive Manager
Comment=Nintendo Switch Archive Manager & Renamer
Exec=nxlibrarian
Icon=nxlibrarian
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=true
EOF

# ── Control file ──────────────────────────────────────────────────────────────
INSTALLED_SIZE=$(du -sk "$PKG_DIR" | cut -f1)
cat > "$PKG_DIR/DEBIAN/control" <<EOF
Package: nxlibrarian
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: amd64
Installed-Size: ${INSTALLED_SIZE}
Maintainer: jackharvest <noreply@github.com>
Description: NX-Librarian — Nintendo Switch Archive Manager & Renamer
 Manage, organize, and verify your Nintendo Switch game collection.
 Supports base games, updates, and DLC with automatic database lookups.
EOF

chmod 755 "$PKG_DIR/DEBIAN"

# ── Build .deb ────────────────────────────────────────────────────────────────
dpkg-deb --build "$PKG_DIR" "$DEB_OUT"
echo "Done: $DEB_OUT"
