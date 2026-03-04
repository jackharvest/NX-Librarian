"""
constants.py — shared configuration for NX-Librarian
"""

import os
import sys

# Cross-platform UI font — Segoe UI on Windows, Helvetica Neue on macOS/Linux
UI_FONT = "Helvetica Neue" if sys.platform == "darwin" else "Segoe UI"

# Font size boost on macOS (Helvetica renders slightly smaller than Segoe UI)
FONT_BOOST = 2 if sys.platform == "darwin" else 0

# Hand cursor — macOS "pointinghand" is the modern native pointer;
# "hand2" is the old X11 hand with the shirt cuff.
HAND_CURSOR = "pointinghand" if sys.platform == "darwin" else "hand2"

APP_NAME      = "NX-Librarian"
APP_VERSION   = "2.2.0"
APP_COPYRIGHT = "© 2026 jackharvest / NX-Librarian Contributors"

# --- File paths ---
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".nxlibrarian_config.ini")
CACHE_FILE  = os.path.join(os.path.expanduser("~"), ".nxlibrarian_cache.json")

CACHE_DURATION = 86400  # 24 hours in seconds

# --- Remote database URLs (blawar/titledb) ---
VERSIONS_DB = "https://raw.githubusercontent.com/blawar/titledb/master/versions.json"
CNMTS_DB    = "https://raw.githubusercontent.com/blawar/titledb/master/cnmts.json"

# Regional title DBs — fetched and merged; US takes precedence on shared titles.
TITLES_DBS = {
    "USA": "https://raw.githubusercontent.com/blawar/titledb/master/US.en.json",
    "EUR": "https://raw.githubusercontent.com/blawar/titledb/master/GB.en.json",
    "JPN": "https://raw.githubusercontent.com/blawar/titledb/master/JP.ja.json",
    "KOR": "https://raw.githubusercontent.com/blawar/titledb/master/KR.ko.json",
    "ASI": "https://raw.githubusercontent.com/blawar/titledb/master/HK.zh.json",
    "CHN": "https://raw.githubusercontent.com/blawar/titledb/master/CN.zh.json",
}

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
