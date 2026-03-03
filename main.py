"""
main.py — NX-Librarian entry point.

Flow:
  1. Show animated splash screen (growing white circle + logo + progress %)
  2. Load/fetch databases in background thread while splash animates
  3. On completion → launch main app window
"""

import os
import sys
import tkinter as tk

# Make sure sibling modules resolve correctly when run from any cwd
sys.path.insert(0, os.path.dirname(__file__))

from splash import SplashScreen
from db     import load_db


def main():
    _norm_v = {}
    _norm_t = {}
    _norm_c = {}

    def _load(progress_cb):
        nonlocal _norm_v, _norm_t, _norm_c
        v, t, c = load_db(force_refresh=False, progress_cb=progress_cb)
        _norm_v = v or {}
        _norm_t = t or {}
        _norm_c = c or {}

    def _launch():
        from app import NXLibrarianApp
        root = tk.Tk()
        NXLibrarianApp(root, norm_v=_norm_v, norm_t=_norm_t, norm_c=_norm_c)
        root.mainloop()

    splash = SplashScreen(on_complete=_launch)
    splash.start(_load)


if __name__ == "__main__":
    main()
