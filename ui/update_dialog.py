"""
ui/update_dialog.py — Auto-update dialog for NX-Librarian.

Styled to match fix_tid_dialog.py — title-bar / content / footer layout,
frame-based progress bar (no Canvas), and the safe grab_set() init sequence
that avoids the Windows black-window bug.
"""

import threading
import tkinter as tk

from constants import UI_FONT, FONT_BOOST, HAND_CURSOR, APP_VERSION
import updater

_F = FONT_BOOST

_T = {
    "bg":         "#0a0a14",
    "bg_card":    "#151d33",
    "bg_hover":   "#1f2847",
    "border":     "#2a3f5f",
    "border_lt":  "#3a4a6f",
    "text":       "#ffffff",
    "text_dim":   "#9ca3af",
    "text_muted": "#6b7280",
    "accent":     "#60a5fa",
    "ok":         "#10b981",
    "warn":       "#f97316",
    "danger":     "#ef4444",
}


class UpdateDialog(tk.Toplevel):
    """
    Modal update dialog.

    Parameters
    ----------
    parent      : tk widget
    version     : str      — new version tag, e.g. "3.1.0"
    asset_url   : str      — direct download URL for the platform asset
    notes       : str      — release notes (markdown text)
    html_url    : str      — GitHub release page URL (unused; kept for API compat)
    quit_fn     : callable — called after apply_and_relaunch to close the app
    """

    def __init__(self, parent, version, asset_url, notes, html_url, quit_fn=None):
        super().__init__(parent)
        self._version   = version
        self._asset_url = asset_url
        self._notes     = notes
        self._quit_fn   = quit_fn or parent.winfo_toplevel().quit

        self.title(f"Update Available — NX-Librarian v{version}")
        self.resizable(False, False)
        self.configure(bg=_T["bg"])
        self.transient(parent)

        self._build()

        # Safe init sequence — matches fix_tid_dialog.py pattern.
        # update_idletasks() lays out geometry without processing events;
        # grab_set() is called only after the window is fully laid out.
        self.update_idletasks()
        root = parent.winfo_toplevel()
        rx, ry = root.winfo_rootx(), root.winfo_rooty()
        rw, rh = root.winfo_width(), root.winfo_height()
        w,  h  = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{rx + (rw - w) // 2}+{ry + (rh - h) // 2}")
        self.grab_set()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        # ── Title bar ──────────────────────────────────────────────────
        title_bar = tk.Frame(self, bg=_T["bg_card"],
                             highlightthickness=1,
                             highlightbackground=_T["border"])
        title_bar.pack(fill="x")

        tk.Label(title_bar,
                 text=f"⬆  UPDATE AVAILABLE — v{self._version}",
                 font=(UI_FONT, 13 + _F, "bold"),
                 fg=_T["accent"], bg=_T["bg_card"],
                 padx=20, pady=14).pack(side="left")

        tk.Label(title_bar,
                 text=f"You have v{APP_VERSION}",
                 font=(UI_FONT, 9 + _F),
                 fg=_T["text_dim"], bg=_T["bg_card"],
                 padx=20).pack(side="right")

        # ── Release notes ──────────────────────────────────────────────
        notes_outer = tk.Frame(self, bg=_T["bg_card"],
                               highlightthickness=1,
                               highlightbackground=_T["border"])
        notes_outer.pack(fill="both", expand=True, pady=(1, 0))

        notes_scroll = tk.Scrollbar(notes_outer, orient="vertical",
                                    bg=_T["bg_hover"])
        notes_scroll.pack(side="right", fill="y")

        self._notes_box = tk.Text(
            notes_outer, height=14, width=60,
            bg=_T["bg_card"], fg=_T["text_dim"],
            insertbackground=_T["text"],
            font=(UI_FONT, 9 + _F), relief="flat", bd=0,
            wrap="word", state="normal",
            yscrollcommand=notes_scroll.set,
            padx=14, pady=10,
        )
        self._notes_box.insert("1.0", self._notes or "(No release notes)")
        self._notes_box.config(state="disabled")
        self._notes_box.pack(side="left", fill="both", expand=True)
        notes_scroll.config(command=self._notes_box.yview)

        # ── Progress bar ───────────────────────────────────────────────
        prog_frame = tk.Frame(self, bg=_T["bg"],
                              highlightthickness=1,
                              highlightbackground=_T["border"])
        prog_frame.pack(fill="x", pady=(1, 0))

        prog_inner = tk.Frame(prog_frame, bg=_T["bg"])
        prog_inner.pack(fill="x", padx=16, pady=10)

        # Track (fixed height container)
        track = tk.Frame(prog_inner, bg=_T["border"], height=10)
        track.pack(fill="x")
        track.pack_propagate(False)

        # Fill bar — relwidth driven by _draw_bar()
        self._bar_fill = tk.Frame(track, bg=_T["accent"])
        self._bar_fill.place(x=0, y=0, relheight=1.0, relwidth=0.0)

        self._pct_lbl = tk.Label(prog_inner, text="",
                                 bg=_T["bg"], fg=_T["text_dim"],
                                 font=(UI_FONT, 8 + _F))
        self._pct_lbl.pack(anchor="e", pady=(2, 0))

        # ── Footer ─────────────────────────────────────────────────────
        footer = tk.Frame(self, bg=_T["bg_card"],
                          highlightthickness=1,
                          highlightbackground=_T["border"])
        footer.pack(fill="x", side="bottom")

        fi = tk.Frame(footer, bg=_T["bg_card"])
        fi.pack(fill="x", padx=16, pady=12)

        self._dl_btn = self._btn(fi, "⬇  Download & Install",
                                 _T["accent"], self._on_download)
        self._dl_btn.pack(side="left", padx=(0, 8))

        self._skip_btn = self._btn(fi, "Skip This Version",
                                   _T["text_dim"], self._on_skip)
        self._skip_btn.pack(side="left", padx=(0, 8))

        self._later_btn = self._btn(fi, "Later",
                                    _T["text_dim"], self.destroy)
        self._later_btn.pack(side="left")

    @staticmethod
    def _btn(parent, text, fg, cmd):
        b = tk.Label(parent, text=text, fg=fg, bg=_T["bg_hover"],
                     font=(UI_FONT, 10 + _F, "bold"),
                     padx=14, pady=6, cursor=HAND_CURSOR, relief="flat")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>",    lambda e: b.config(bg=_T["border_lt"]))
        b.bind("<Leave>",    lambda e: b.config(bg=_T["bg_hover"]))
        return b

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    def _set_progress(self, pct: int):
        """Thread-safe progress update."""
        self.after(0, self._draw_bar, pct)

    def _draw_bar(self, pct: int):
        self._bar_fill.place(relwidth=pct / 100)
        self._pct_lbl.config(text=f"{pct}%" if pct > 0 else "")

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    def _on_download(self):
        self._dl_btn.config(text="Downloading…", fg=_T["text_dim"], cursor="")
        self._dl_btn.unbind("<Button-1>")
        self._skip_btn.unbind("<Button-1>")
        self._later_btn.unbind("<Button-1>")

        def _worker():
            path = updater.download_release(self._asset_url, self._set_progress)
            self.after(0, self._on_download_complete, path)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_download_complete(self, path):
        if path is None:
            self._dl_btn.config(text="Download failed — try again",
                                fg=_T["danger"])
            self._dl_btn.bind("<Button-1>", lambda e: self._on_download())
            return

        self._draw_bar(100)
        self._dl_btn.config(text="Installing…", fg=_T["ok"])
        self.after(400, lambda: updater.apply_and_relaunch(path, self._quit_fn))

    def _on_skip(self):
        updater.save_update_prefs(skip_version=self._version)
        self.destroy()
