#!/usr/bin/env bash
# build_scripts/create_appimage.sh
#
# Assembles a Linux .AppImage from the PyInstaller one-file binary.
#
# Prerequisites:
#   - PyInstaller binary at dist/NX-Librarian
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
BINARY="$DIST/NX-Librarian"
APPDIR="$DIST/AppDir"
APPIMAGETOOL="$DIST/appimagetool"
OUTPUT="$DIST/NX-Librarian-x86_64.AppImage"

# ── 1. Verify binary ──────────────────────────────────────────────────────────
if [ ! -f "$BINARY" ]; then
    echo "ERROR: PyInstaller binary not found at $BINARY"
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
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp "$BINARY" "$APPDIR/usr/bin/NX-Librarian"

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

# Icon (use logo.png as the app icon; requires it be 256x256 or similar)
cp "$ROOT/logo.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/nxlibrarian.png"

# AppDir root symlinks required by AppImage spec
cp "$APPDIR/usr/share/applications/nxlibrarian.desktop" "$APPDIR/"
cp "$APPDIR/usr/share/icons/hicolor/256x256/apps/nxlibrarian.png" "$APPDIR/"
ln -sf usr/bin/NX-Librarian "$APPDIR/AppRun"

# ── 4. Build AppImage ─────────────────────────────────────────────────────────
echo "Building AppImage …"
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$OUTPUT"

echo ""
echo "Done: $OUTPUT"
