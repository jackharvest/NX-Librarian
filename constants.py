"""
constants.py — shared configuration for NX-Librarian
"""

import os
import re
import sys

# Cross-platform UI font — Segoe UI on Windows, Helvetica Neue on macOS/Linux
UI_FONT = "Helvetica Neue" if sys.platform == "darwin" else "Segoe UI"

# Font size boost on macOS (Helvetica renders slightly smaller than Segoe UI)
FONT_BOOST = 2 if sys.platform == "darwin" else 0

# Hand cursor — macOS "pointinghand" is the modern native pointer;
# "hand2" is the old X11 hand with the shirt cuff.
HAND_CURSOR = "pointinghand" if sys.platform == "darwin" else "hand2"

APP_NAME      = "NX-Librarian"
APP_VERSION   = "3.0.0-beta.9"
APP_COPYRIGHT = "© 2026 jackharvest / NX-Librarian Contributors"
GITHUB_REPO   = "jackharvest/NX-Librarian"

# --- File paths ---
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".nxlibrarian_config.ini")
CACHE_FILE  = os.path.join(os.path.expanduser("~"), ".nxlibrarian_cache.json")

CACHE_DURATION = 86400  # 24 hours in seconds

# --- Database mirror configuration ---
# Each entry: display label → base URL (trailing slash optional)
# Files appended: versions.json, cnmts.json, US.en.json, GB.en.json, etc.
DB_MIRRORS = {
    "GitHub (Primary)": "https://raw.githubusercontent.com/blawar/titledb/master",
    "jsDelivr CDN":     "https://cdn.jsdelivr.net/gh/blawar/titledb@master",
    "Custom":           None,   # user-supplied; stored in config as db_mirror_custom
}
DEFAULT_MIRROR = "GitHub (Primary)"

# Files within each mirror base
_DB_FILES = {
    "versions": "versions.json",
    "cnmts":    "cnmts.json",
    "titles": {
        "USA": "US.en.json",
        "EUR": "GB.en.json",
        "JPN": "JP.ja.json",
        "KOR": "KR.ko.json",
        "ASI": "HK.zh.json",
        "CHN": "CN.zh.json",
    },
}


def get_db_urls(base: str) -> dict:
    """Return full URL dict for all DB files given a mirror base URL."""
    base = base.rstrip("/")
    return {
        "versions": f"{base}/{_DB_FILES['versions']}",
        "cnmts":    f"{base}/{_DB_FILES['cnmts']}",
        "titles":   {r: f"{base}/{f}" for r, f in _DB_FILES["titles"].items()},
    }


# Convenience constants derived from the default mirror (backward compat)
_DEFAULT_URLS = get_db_urls(DB_MIRRORS[DEFAULT_MIRROR])
VERSIONS_DB = _DEFAULT_URLS["versions"]
CNMTS_DB    = _DEFAULT_URLS["cnmts"]
TITLES_DBS  = _DEFAULT_URLS["titles"]

# --- Filename quality check ---
_RE_BRACKET_TID    = re.compile(r'\[([01][0-9A-Fa-f]{15})\]')
_RE_BRACKET_VER    = re.compile(r'\[v\d+\]', re.IGNORECASE)
_RE_BRACKET_REGION = re.compile(
    r'\[(USA|EUR|JPN|KOR|CHN|ASI|TWN|WORLD|UKV|GLB|US|EU|JP|UK)\]',
    re.IGNORECASE)
_RE_DISPLAY_VER    = re.compile(r'(?<![A-Za-z])[vV]\d[\d.]*')   # e.g. v1.0.0, v2.3
_RE_ANY_BRACKET    = re.compile(r'\[')


def is_clean_filename(fname: str) -> bool:
    """
    Return True if the filename follows the expected convention:
        Game Name [TitleID][vVERSION].ext
    An optional region tag like [USA] or [EUR] is also accepted.
    Flags extra tokens like [APP], [DLC], v1.0.0, etc. as bad names.
    """
    stem = os.path.splitext(fname)[0]
    if not _RE_BRACKET_TID.search(stem):
        return False
    if not _RE_BRACKET_VER.search(stem):
        return False
    # Strip the expected tokens (region optional) then check nothing else remains
    cleaned = _RE_BRACKET_TID.sub('', stem)
    cleaned = _RE_BRACKET_VER.sub('', cleaned)
    cleaned = _RE_BRACKET_REGION.sub('', cleaned)
    if _RE_ANY_BRACKET.search(cleaned):   # extra [whatever] token
        return False
    if _RE_DISPLAY_VER.search(cleaned):   # leftover v1.0.0 style string
        return False
    return True


# --- Title ID classification ---
# Switch Title IDs are 16 hex chars. The type is encoded in the last 3 hex chars:
#   Base game : tid[-3:] == '000'
#   Update    : tid[-3:] == '800'
#   DLC       : anything else (e.g. '001', '002', '12d', '100', '200', ...)
# DLC TIDs can have tid[13]='0' (e.g. ...7002) or non-zero (e.g. ...12d),
# so checking only tid[13] misclassifies ~90 % of real DLC as base games.
def classify_title_id(tid: str) -> str:
    """Return 'base', 'update', or 'dlc' for a 16-char Title ID string."""
    tid = tid.lower()
    if len(tid) != 16:
        return "unknown"
    suffix = tid[-3:]
    if suffix == "000":
        return "base"
    if suffix == "800":
        return "update"
    return "dlc"

# --- Region ---
KNOWN_REGIONS = {"USA", "EUR", "JPN", "KOR", "CHN", "TWN", "ASI", "WORLD", "UKV", "GLB"}

# Short-form aliases found in filenames (e.g. [US], [EU], [JP])
REGION_ALIASES = {
    "US": "USA",
    "EU": "EUR",
    "JP": "JPN",
    "UK": "UKV",
}

REGION_FLAGS = {
    "USA":   "● USA",
    "EUR":   "● EUR",
    "JPN":   "● JPN",
    "KOR":   "● KOR",
    "CHN":   "● CHN",
    "ASI":   "● ASI",
    "TWN":   "● TWN",
    "WORLD": "● WLD",
    "UKV":   "● UKV",
    "GLB":   "● GLB",
}

# --- UI colours ---
COLOR_BG        = "#ffffff"
COLOR_ACCENT    = "#0078d4"   # blue  — primary action
COLOR_GREEN     = "#2e7d32"   # green — edit mode / positive
COLOR_RED       = "#d32f2f"   # red   — outdated / danger
COLOR_AMBER     = "#e65100"   # amber — unverified
COLOR_PURPLE    = "#7b61ff"   # purple — base game tag
COLOR_MUTED     = "#888888"
COLOR_ROW_ALT   = "#f9f9f9"

# Treeview row tags
TAG_OUTDATED = "outdated"
TAG_LATEST   = "latest"
TAG_BASE     = "base"
TAG_UNKNOWN  = "unknown"
TAG_WARN     = "warn"
TAG_SKIP     = "skip"
