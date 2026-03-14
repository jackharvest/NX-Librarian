"""
ui/shortcuts_dialog.py — Keyboard shortcuts reference popup.
"""

import tkinter as tk
from constants import UI_FONT, FONT_BOOST, HAND_CURSOR
from ui.popup_utils import apply_window_theme

_F  = FONT_BOOST
_BG = "#0a0a14"

_C = {
    "header_bg":   "#0d1220",
    "accent":      "#60a5fa",
    "white":       "#ffffff",
    "body":        "#c0c2d8",
    "dim":         "#6b7280",
    "section_bar": "#1e2d4a",
    "key_bg":      "#1e2d4a",
}

_SHORTCUTS = [
    ("Ctrl+S",  "Scan library"),
    ("Ctrl+O",  "Browse folder"),
    ("Ctrl+F",  "Focus search"),
    ("F5",      "Refresh"),
    ("ESC",     "Back to mode select"),
    ("F11",     "Toggle fullscreen"),
    ("Ctrl+Q",  "Quit"),
]


def show_shortcuts(parent):
    """Open the Keyboard Shortcuts reference window."""
    win = tk.Toplevel(parent)
    win.title("Keyboard Shortcuts — NX-Librarian")
    win.configure(bg=_BG)
    win.resizable(False, False)

    W, H = 400, 390
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
    apply_window_theme(win)
    win.grab_set()

    # ── Header ────────────────────────────────────────────────────────────
    hdr = tk.Frame(win, bg=_C["header_bg"])
    hdr.pack(fill="x")

    tk.Label(hdr, text="⌨  KEYBOARD SHORTCUTS",
             bg=_C["header_bg"], fg=_C["white"],
             font=(UI_FONT, 14 + _F, "bold")).pack(pady=(20, 18))
    tk.Frame(hdr, bg=_C["accent"], height=2).pack(fill="x")

    # ── Shortcut rows ─────────────────────────────────────────────────────
    body = tk.Frame(win, bg=_BG)
    body.pack(fill="both", expand=True, padx=32, pady=20)

    for key, desc in _SHORTCUTS:
        row = tk.Frame(body, bg=_BG)
        row.pack(fill="x", pady=5)

        tk.Label(row, text=key,
                 bg=_C["key_bg"], fg=_C["accent"],
                 font=(UI_FONT, 9 + _F, "bold"),
                 width=10, anchor="center",
                 padx=8, pady=5).pack(side="left")

        tk.Label(row, text=desc,
                 bg=_BG, fg=_C["body"],
                 font=(UI_FONT, 9 + _F),
                 anchor="w").pack(side="left", padx=(16, 0))

    # ── Footer ────────────────────────────────────────────────────────────
    foot = tk.Frame(win, bg=_C["header_bg"])
    foot.pack(fill="x", side="bottom")
    tk.Frame(foot, bg=_C["accent"], height=2).pack(fill="x")
    btn = tk.Label(foot, text="CLOSE",
                   bg=_C["header_bg"], fg=_C["accent"],
                   font=(UI_FONT, 9 + _F, "bold"),
                   padx=28, pady=10, cursor=HAND_CURSOR)
    btn.pack(pady=6)
    btn.bind("<Button-1>", lambda e: win.destroy())
    btn.bind("<Enter>",    lambda e: btn.config(bg=_C["section_bar"]))
    btn.bind("<Leave>",    lambda e: btn.config(bg=_C["header_bg"]))
