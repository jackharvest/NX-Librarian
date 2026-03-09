#!/usr/bin/env bash
# build_scripts/create_appimage.sh
#
# Assembles a Linux .AppImage from the PyInstaller onedir bundle.
#
# Prerequisites:
#   - PyInstaller onedir output at dist/NX-Librarian/
#   - appimagetool available (downloaded here if absent)
#   - FUSE support on the build machine (or --appimage-extract-and-run)
#
# Usage (from project root):
#   bash build_scripts/create_appimage.sh
#
# Output: dist/NX-Librarian-x86_64.AppImage

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
BUNDLE_DIR="$DIST/NX-Librarian"
BINARY="$BUNDLE_DIR/NX-Librarian"
APPDIR="$DIST/AppDir"
APPIMAGETOOL="$DIST/appimagetool"
OUTPUT="$DIST/NX-Librarian-x86_64.AppImage"

# ── 1. Verify onedir bundle ───────────────────────────────────────────────────
if [ ! -d "$BUNDLE_DIR" ] || [ ! -f "$BINARY" ]; then
    echo "ERROR: PyInstaller onedir bundle not found at $BUNDLE_DIR"
    echo "       Run 'pyinstaller main.spec' first."
    exit 1
fi
chmod +x "$BINARY"

# ── 2. Download appimagetool if needed ────────────────────────────────────────
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "Downloading appimagetool …"
    curl -L -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

# ── 3. Assemble AppDir ────────────────────────────────────────────────────────
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib/nxlibrarian"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copy entire onedir bundle into usr/lib/nxlibrarian/
cp -r "$BUNDLE_DIR/." "$APPDIR/usr/lib/nxlibrarian/"

# AppRun launches the bundled binary with $APPDIR resolved at runtime
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/bash
exec "$(dirname "$(readlink -f "$0")")/usr/lib/nxlibrarian/NX-Librarian" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# Desktop entry
cat > "$APPDIR/usr/share/applications/nxlibrarian.desktop" <<EOF
[Desktop Entry]
Name=NX-Librarian
Comment=Nintendo Switch Archive Manager & Renamer
Exec=NX-Librarian
Icon=nxlibrarian
Type=Application
Categories=Utility;
EOF

# Icon
cp "$ROOT/logo.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/nxlibrarian.png"

# AppDir root symlinks required by AppImage spec
cp "$APPDIR/usr/share/applications/nxlibrarian.desktop" "$APPDIR/"
cp "$APPDIR/usr/share/icons/hicolor/256x256/apps/nxlibrarian.png" "$APPDIR/"

# ── 4. Build AppImage ─────────────────────────────────────────────────────────
echo "Building AppImage …"
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$OUTPUT"

echo ""
echo "Done: $OUTPUT"
