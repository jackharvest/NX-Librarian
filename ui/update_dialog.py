"""
ui/update_dialog.py — Auto-update dialog for NX-Librarian.

Styled to match the app's dark theme. Downloads the release in a
background thread and calls updater.apply_and_relaunch() on completion.
"""

import threading
import tkinter as tk
from tkinter import messagebox

from constants import UI_FONT, FONT_BOOST, HAND_CURSOR, APP_VERSION
import updater

_F = FONT_BOOST

# Colours (mirrors base_screen.py THEME)
_BG       = "#0a0a14"
_BG2      = "#151d33"
_BG3      = "#1f2847"
_FG       = "#ffffff"
_FG2      = "#9ca3af"
_ACCENT   = "#60a5fa"
_ORANGE   = "#f97316"
_GREEN    = "#10b981"
_BAR_FG   = "#60a5fa"
_BAR_BG   = "#1f2847"


class UpdateDialog(tk.Toplevel):
    """
    Modal update dialog.

    Parameters
    ----------
    parent      : tk widget
    version     : str     — new version tag, e.g. "3.1.0"
    asset_url   : str     — direct download URL for the platform asset
    notes       : str     — release notes (markdown text)
    html_url    : str     — GitHub release page URL (for Skip)
    quit_fn     : callable — called after apply_and_relaunch to close the app
    """

    def __init__(self, parent, version, asset_url, notes, html_url, quit_fn=None):
        super().__init__(parent)
        self._version   = version
        self._asset_url = asset_url
        self._notes     = notes
        self._html_url  = html_url
        self._quit_fn   = quit_fn or parent.winfo_toplevel().quit

        self.title(f"Update Available — NX-Librarian v{version}")
        self.configure(bg=_BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build()

        # Centre over parent
        self.update_idletasks()
        pw = parent.winfo_rootx()
        py = parent.winfo_rooty()
        ph = parent.winfo_height()
        pw2 = parent.winfo_width()
        w, h = self.winfo_width(), self.winfo_height()
        x = pw + (pw2 - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        pad = dict(padx=24, pady=8)

        # Title
        tk.Label(self, text=f"⬆  Update Available — NX-Librarian v{self._version}",
                 bg=_BG, fg=_ACCENT, font=(UI_FONT, 14 + _F, "bold")).pack(**pad, pady=(20, 4))

        tk.Label(self, text=f"You have v{APP_VERSION}",
                 bg=_BG, fg=_FG2, font=(UI_FONT, 10 + _F)).pack(padx=24, pady=(0, 8))

        # Release notes
        notes_frame = tk.Frame(self, bg=_BG2, bd=1, relief="flat")
        notes_frame.pack(padx=24, pady=4, fill="both", expand=True)

        notes_scroll = tk.Scrollbar(notes_frame, orient="vertical", bg=_BG3)
        notes_scroll.pack(side="right", fill="y")

        self._notes_box = tk.Text(
            notes_frame, height=12, width=62,
            bg=_BG2, fg=_FG2, insertbackground=_FG,
            font=(UI_FONT, 9 + _F), relief="flat", bd=0,
            wrap="word", state="normal",
            yscrollcommand=notes_scroll.set,
        )
        self._notes_box.insert("1.0", self._notes or "(No release notes)")
        self._notes_box.config(state="disabled")
        self._notes_box.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        notes_scroll.config(command=self._notes_box.yview)

        # Progress bar (Canvas-drawn)
        self._bar_canvas = tk.Canvas(self, height=18, bg=_BG, highlightthickness=0)
        self._bar_canvas.pack(padx=24, pady=(12, 4), fill="x")
        self._bar_pct_lbl = tk.Label(self, text="", bg=_BG, fg=_FG2,
                                     font=(UI_FONT, 9 + _F))
        self._bar_pct_lbl.pack(padx=24)

        self._draw_bar(0)

        # Buttons
        btn_frame = tk.Frame(self, bg=_BG)
        btn_frame.pack(padx=24, pady=(12, 20))

        self._dl_btn = self._make_btn(
            btn_frame, "⬇  Download & Install", _ACCENT, self._on_download)
        self._dl_btn.pack(side="left", padx=(0, 8))

        self._skip_btn = self._make_btn(
            btn_frame, "Skip This Version", _FG2, self._on_skip)
        self._skip_btn.pack(side="left", padx=(0, 8))

        self._later_btn = self._make_btn(
            btn_frame, "Later", _FG2, self.destroy)
        self._later_btn.pack(side="left")

    @staticmethod
    def _make_btn(parent, text, fg, cmd):
        btn = tk.Label(parent, text=text, fg=fg, bg="#1f2847",
                       font=(UI_FONT, 10 + _F, "bold"),
                       padx=14, pady=6, cursor=HAND_CURSOR, relief="flat")
        btn.bind("<Button-1>", lambda e: cmd())
        btn.bind("<Enter>", lambda e: btn.config(bg="#2a3f5f"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#1f2847"))
        return btn

    # ------------------------------------------------------------------
    # Progress bar drawing
    # ------------------------------------------------------------------

    def _draw_bar(self, pct: int):
        self._bar_canvas.update_idletasks()
        w = self._bar_canvas.winfo_width() or 500
        h = 18
        self._bar_canvas.delete("all")
        # Track
        self._bar_canvas.create_rectangle(0, 4, w, h - 4,
                                          fill=_BAR_BG, outline="", width=0)
        # Fill
        fill_w = int(w * pct / 100)
        if fill_w > 0:
            self._bar_canvas.create_rectangle(0, 4, fill_w, h - 4,
                                              fill=_BAR_FG, outline="", width=0)
        self._bar_pct_lbl.config(text=f"{pct}%")

    def _set_progress(self, pct: int):
        """Thread-safe progress update via after()."""
        self.after(0, self._draw_bar, pct)

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    def _on_download(self):
        """Start download in background thread."""
        self._dl_btn.config(text="Downloading…", fg=_FG2, cursor="")
        self._dl_btn.unbind("<Button-1>")
        self._skip_btn.unbind("<Button-1>")
        self._later_btn.unbind("<Button-1>")

        def _worker():
            path = updater.download_release(self._asset_url, self._set_progress)
            self.after(0, self._on_download_complete, path)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_download_complete(self, path):
        if path is None:
            self._dl_btn.config(text="Download failed — try again", fg="#ef4444")
            self._dl_btn.bind("<Button-1>", lambda e: self._on_download())
            return

        self._draw_bar(100)
        self._dl_btn.config(text="Installing…", fg=_GREEN)
        # Brief pause so user sees 100%
        self.after(400, lambda: updater.apply_and_relaunch(path, self._quit_fn))

    def _on_skip(self):
        updater.save_update_prefs(skip_version=self._version)
        self.destroy()
