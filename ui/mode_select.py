"""
ui/mode_select.py — Full-height Nintendo Switch color panel selector.

Three full-screen panels side by side:
  Red   → Base Games
  Blue  → Updates
  Green → DLC & Add-Ons
"""

import tkinter as tk
from constants import UI_FONT, FONT_BOOST

_F = FONT_BOOST

# Nintendo Switch inspired panel colors.
# bg_h is a noticeably lighter/brighter shade for obvious hover feedback.
PANEL_CONFIG = {
    "base": {
        "title": "BASE GAMES",
        "emoji": "🎮",
        "sub":   "NSP  ·  XCI",
        "bg":    "#B8000F",
        "bg_h":  "#F0001A",   # vibrant bright red on hover
    },
    "updates": {
        "title": "UPDATES",
        "emoji": "🔼",
        "sub":   "VERSION CONTROL",
        "bg":    "#0050A8",
        "bg_h":  "#0077FF",   # bright blue on hover
    },
    "dlc": {
        "title": "DLC & ADD-ONS",
        "emoji": "🎁",
        "sub":   "ADD-ON CONTENT",
        "bg":    "#007A33",
        "bg_h":  "#00B84A",   # bright green on hover
    },
}

MODE_ORDER = ["base", "updates", "dlc"]


class ColorPanel(tk.Frame):
    """Full-height clickable color panel with obvious hover highlight."""

    def __init__(self, parent, mode, cfg, on_select, **kwargs):
        super().__init__(parent, bg=cfg["bg"], cursor="hand2", **kwargs)
        self.mode      = mode
        self.cfg       = cfg
        self.on_select = on_select
        self._bg       = cfg["bg"]
        self._bg_h     = cfg["bg_h"]
        self._bg_widgets   = []   # every widget that needs bg updated
        self._sub_labels   = []   # subtitle labels — fg also changes
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _reg(self, widget, is_sub=False):
        """Register widget for hover updates and return it."""
        self._bg_widgets.append(widget)
        if is_sub:
            self._sub_labels.append(widget)
        return widget

    def _build(self):
        self._reg(self)

        # Top spacer — pushes content to vertical center
        self._reg(tk.Frame(self, bg=self._bg, cursor="hand2")).pack(
            fill="both", expand=True)

        # Centered content block
        c = self._reg(tk.Frame(self, bg=self._bg, cursor="hand2"))
        c.pack(fill="x", padx=40)

        self._reg(tk.Label(c, text=self.cfg["emoji"],
                           font=("Arial", 72 + _F * 2),
                           bg=self._bg, cursor="hand2")).pack(anchor="center")

        self._reg(tk.Label(c, text=self.cfg["title"],
                           font=(UI_FONT, 26 + _F, "bold"),
                           fg="#ffffff", bg=self._bg,
                           cursor="hand2")).pack(anchor="center", pady=(22, 0))

        # Subtitle — fg changes on hover for extra clarity
        self._reg(tk.Label(c, text=self.cfg["sub"],
                           font=(UI_FONT, 11 + _F),
                           fg="#aaaaaa", bg=self._bg,
                           cursor="hand2"),
                  is_sub=True).pack(anchor="center", pady=(10, 0))

        # Bottom spacer
        self._reg(tk.Frame(self, bg=self._bg, cursor="hand2")).pack(
            fill="both", expand=True)

        # Wire click + hover to every registered widget
        for w in self._bg_widgets:
            try:
                w.bind("<Button-1>", lambda e, m=self.mode: self.on_select(m))
                w.bind("<Enter>",    lambda e: self._set_hover(True))
                w.bind("<Leave>",    lambda e: self._on_leave(e))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Hover
    # ------------------------------------------------------------------

    def _set_hover(self, on):
        bg = self._bg_h if on else self._bg
        for w in self._bg_widgets:
            try:
                w.config(bg=bg)
            except Exception:
                pass
        # Subtitle: dim grey at rest → bright white on hover
        fg_sub = "#ffffff" if on else "#aaaaaa"
        for w in self._sub_labels:
            try:
                w.config(fg=fg_sub)
            except Exception:
                pass

    def _on_leave(self, event):
        """Only de-hover when cursor truly exits the panel bounds."""
        try:
            px = self.winfo_rootx()
            py = self.winfo_rooty()
            pw = self.winfo_width()
            ph = self.winfo_height()
            if not (px <= event.x_root <= px + pw and
                    py <= event.y_root <= py + ph):
                self._set_hover(False)
        except Exception:
            self._set_hover(False)


class ModeSelectScreen(tk.Frame):
    """Three full-height Nintendo Switch color panels, exactly equal width."""

    def __init__(self, parent, on_select, logo_img=None, **kwargs):
        super().__init__(parent, bg="#0a0a14", **kwargs)
        self._on_select = on_select
        self._build()

    def _build(self):
        container = tk.Frame(self, bg="#000000")
        container.pack(fill="both", expand=True)

        # uniform="panels" forces all three columns to the same width
        # regardless of content — this is the key fix for unequal sizing.
        for i in range(3):
            container.columnconfigure(i, weight=1, uniform="panels")
        container.rowconfigure(0, weight=1)

        for idx, mode in enumerate(MODE_ORDER):
            panel = ColorPanel(
                container, mode, PANEL_CONFIG[mode], self._on_select
            )
            # 2px black gap between panels (container bg shows through)
            panel.grid(row=0, column=idx, sticky="nsew",
                       padx=(0, 2) if idx < len(MODE_ORDER) - 1 else 0)


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1200x700")

    def _test(mode):
        print(f"Selected: {mode}")

    ModeSelectScreen(root, _test).pack(fill="both", expand=True)
    root.mainloop()
