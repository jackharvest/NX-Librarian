# -*- mode: python ; coding: utf-8 -*-
#
# main.spec — PyInstaller spec for NX-Librarian
#
# Usage:
#   pyinstaller main.spec
#
# Produces:
#   dist/NX-Librarian.exe       (Windows)
#   dist/NX-Librarian.app       (macOS — then packaged into .dmg by build scripts)
#   dist/NX-Librarian           (Linux  — then wrapped into .AppImage by build scripts)

import sys
import os

block_cipher = None

datas = [
    ('logo.png',                 '.'),
    ('logo_tophalf.png',         '.'),
    ('logo_fullbar_thinner.png', '.'),
    ('assets',                   'assets'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PIL._tkinter_finder',
        'requests',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
        'configparser',
        'threading',
        'json',
        'hashlib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Windows / Linux: single-file EXE / binary ─────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NX-Librarian',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                          # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Icons — provide both; PyInstaller picks the right one per platform
    icon='icon.ico' if sys.platform == 'win32' else (
         'icon.icns' if sys.platform == 'darwin' else None),
)

# ── macOS: .app bundle (in addition to the bare binary above) ─────────────────
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='NX-Librarian.app',
        icon='icon.icns',
        bundle_identifier='com.jackharvest.nxlibrarian',
        info_plist={
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.13.0',
            'NSRequiresAquaSystemAppearance': False,
            'CFBundleShortVersionString': '3.0.0',
            'CFBundleVersion': '3.0.0',
            'CFBundleName': 'NX-Librarian',
            'CFBundleDisplayName': 'NX-Librarian',
        },
    )
