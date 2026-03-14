"""
ui/about_dialog.py — About and Up-to-date dialogs for NX-Librarian.
"""

import tkinter as tk
from constants import UI_FONT, FONT_BOOST, APP_VERSION, APP_COPYRIGHT, HAND_CURSOR
from ui.popup_utils import apply_window_theme

_F  = FONT_BOOST
_BG = "#0a0a14"

_C = {
    "header_bg":   "#0d1220",
    "accent":      "#60a5fa",
    "ok":          "#10b981",
    "white":       "#ffffff",
    "body":        "#c0c2d8",
    "dim":         "#6b7280",
    "section_bar": "#1e2d4a",
}


def _close_footer(win, accent_color=None):
    """Accent-bar + CLOSE button footer, matching credits.py style."""
    color = accent_color or _C["accent"]
    foot = tk.Frame(win, bg=_C["header_bg"])
    foot.pack(fill="x", side="bottom")
    tk.Frame(foot, bg=color, height=2).pack(fill="x")
    btn = tk.Label(foot, text="CLOSE",
                   bg=_C["header_bg"], fg=color,
                   font=(UI_FONT, 9 + _F, "bold"),
                   padx=28, pady=10, cursor=HAND_CURSOR)
    btn.pack(pady=6)
    btn.bind("<Button-1>", lambda e: win.destroy())
    btn.bind("<Enter>",    lambda e: btn.config(bg=_C["section_bar"]))
    btn.bind("<Leave>",    lambda e: btn.config(bg=_C["header_bg"]))


def show_about(parent):
    """Open the About NX-Librarian window."""
    win = tk.Toplevel(parent)
    win.title("About — NX-Librarian")
    win.configure(bg=_BG)
    win.resizable(False, False)

    W, H = 460, 330
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
    apply_window_theme(win)
    win.grab_set()

    # ── Header ────────────────────────────────────────────────────────────
    hdr = tk.Frame(win, bg=_C["header_bg"])
    hdr.pack(fill="x")

    tk.Label(hdr, text="NX-LIBRARIAN",
             bg=_C["header_bg"], fg=_C["white"],
             font=(UI_FONT, 20 + _F, "bold")).pack(pady=(22, 0))
    tk.Label(hdr, text="Nintendo Switch Archive Manager & Renamer",
             bg=_C["header_bg"], fg=_C["accent"],
             font=(UI_FONT, 9 + _F, "bold")).pack()
    tk.Label(hdr, text=f"v{APP_VERSION}",
             bg=_C["header_bg"], fg=_C["dim"],
             font=(UI_FONT, 9 + _F)).pack(pady=(2, 14))
    tk.Frame(hdr, bg=_C["accent"], height=2).pack(fill="x")

    # ── Body ──────────────────────────────────────────────────────────────
    body = tk.Frame(win, bg=_BG)
    body.pack(fill="both", expand=True, padx=36, pady=22)

    lines = [
        ("Manage, organize, and verify your Switch game collection —",          _C["body"]),
        ("base games, updates, and DLC.",                                        _C["body"]),
        ("",                                                                      None),
        ("Art Mode overlays in-row banner art sourced from the Nintendo",        _C["body"]),
        ("eShop CDN via blawar/titledb.",                                        _C["body"]),
        ("",                                                                      None),
        (APP_COPYRIGHT,                                                           _C["dim"]),
    ]
    for text, fg in lines:
        if fg is None:
            tk.Frame(body, bg=_BG, height=6).pack()
        else:
            tk.Label(body, text=text,
                     bg=_BG, fg=fg,
                     font=(UI_FONT, 9 + _F),
                     anchor="w", justify="left").pack(fill="x")

    _close_footer(win)


def show_uptodate(parent):
    """Open the 'You're already up to date' dialog."""
    win = tk.Toplevel(parent)
    win.title("Up to Date — NX-Librarian")
    win.configure(bg=_BG)
    win.resizable(False, False)

    W, H = 400, 220
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
    apply_window_theme(win)
    win.grab_set()

    # ── Header ────────────────────────────────────────────────────────────
    hdr = tk.Frame(win, bg=_C["header_bg"])
    hdr.pack(fill="x")

    tk.Label(hdr, text="✓  UP TO DATE",
             bg=_C["header_bg"], fg=_C["ok"],
             font=(UI_FONT, 14 + _F, "bold")).pack(pady=(20, 0))
    tk.Label(hdr, text=f"NX-Librarian  v{APP_VERSION}",
             bg=_C["header_bg"], fg=_C["dim"],
             font=(UI_FONT, 9 + _F)).pack(pady=(4, 16))
    tk.Frame(hdr, bg=_C["ok"], height=2).pack(fill="x")

    # ── Body ──────────────────────────────────────────────────────────────
    body = tk.Frame(win, bg=_BG)
    body.pack(fill="both", expand=True)

    tk.Label(body,
             text="You're already running the latest version.",
             bg=_BG, fg=_C["body"],
             font=(UI_FONT, 10 + _F)).pack(expand=True)

    _close_footer(win, accent_color=_C["ok"])
