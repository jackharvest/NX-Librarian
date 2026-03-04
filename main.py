"""
main.py — NX-Librarian entry point.

Flow:
  1. Show animated splash screen (growing white circle + logo + progress %)
  2. Load/fetch databases in background thread (0–60 % of progress bar)
  3. If Pre-Scan is enabled and folder paths are cached, scan each folder
     during the splash (60–97 % of progress bar)
  4. On completion → launch main app window with data already loaded
"""

import os
import sys
import configparser
import tkinter as tk

# Make sure sibling modules resolve correctly when run from any cwd
sys.path.insert(0, os.path.dirname(__file__))

from splash import SplashScreen
from db     import load_db
from constants import CONFIG_FILE


def _read_prescan_config():
    """Return (pre_scan_enabled, {mode: folder_path}) from config."""
    pre_scan = True
    folders  = {}
    try:
        cfg = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            cfg.read(CONFIG_FILE)
            if cfg.has_option("Settings", "pre_scan"):
                pre_scan = cfg.getboolean("Settings", "pre_scan")
            for mode in ("base", "updates", "dlc"):
                path = cfg.get("Folders", f"folder_{mode}", fallback="").strip()
                if path and os.path.isdir(path):
                    folders[mode] = path
    except Exception:
        pass
    return pre_scan, folders


def main():
    _norm_v       = {}
    _norm_t       = {}
    _norm_c       = {}
    _prescan_data = {}   # {mode: (all_data, missing, improper, unknown)}

    def _load(progress_cb):
        nonlocal _norm_v, _norm_t, _norm_c

        pre_scan, folders = _read_prescan_config()
        has_folders = bool(folders)

        # DB loading occupies 0–60 % when pre-scan will follow, else 0–100 %
        db_end = 60.0 if (pre_scan and has_folders) else 100.0

        v, t, c = load_db(
            force_refresh=False,
            progress_cb=lambda p: progress_cb(p * db_end / 100.0),
        )
        _norm_v = v or {}
        _norm_t = t or {}
        _norm_c = c or {}

        if not pre_scan or not has_folders:
            progress_cb(100)
            return

        # Pre-scan each cached folder (60–97 %)
        from prescan import scan_base, scan_updates, scan_dlc

        scan_fns = {
            "base":    lambda f: scan_base(f, _norm_v, _norm_t),
            "updates": lambda f: scan_updates(f, _norm_v, _norm_t),
            "dlc":     lambda f: scan_dlc(f, _norm_t, _norm_c),
        }
        modes     = [m for m in ("base", "updates", "dlc") if m in folders]
        step      = (97.0 - db_end) / max(len(modes), 1)

        for i, mode in enumerate(modes):
            try:
                _prescan_data[mode] = scan_fns[mode](folders[mode])
            except Exception:
                pass
            progress_cb(db_end + step * (i + 1))

        progress_cb(100)

    def _launch():
        from app import NXLibrarianApp
        root = tk.Tk()
        NXLibrarianApp(root,
                       norm_v=_norm_v,
                       norm_t=_norm_t,
                       norm_c=_norm_c,
                       prescan_data=_prescan_data)
        root.mainloop()

    splash = SplashScreen(on_complete=_launch)
    splash.start(_load)


if __name__ == "__main__":
    main()
