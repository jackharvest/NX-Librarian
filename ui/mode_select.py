"""
ui/mode_select.py — Full-height Nintendo Switch color panel selector.

Three full-screen panels side by side:
  Red   → Base Games
  Blue  → Updates
  Green → DLC & Add-Ons
"""

import configparser
import os
import tkinter as tk
from constants import UI_FONT, FONT_BOOST, HAND_CURSOR, APP_VERSION, APP_COPYRIGHT, CONFIG_FILE
from ui.tooltip import ComicTooltip
import ui.tooltip as _tooltip

_F = FONT_BOOST

# Nintendo Switch inspired panel colors.
# bg_h is a noticeably lighter/brighter shade for obvious hover feedback.
PANEL_CONFIG = {
    "base": {
        "title":   "BASE GAMES",
        "emoji":   "🎮",
        "sub":     "NSP  ·  XCI",
        "bg":      "#B8000F",
        "bg_h":    "#F0001A",
        "tooltip": "Your main game archive. Browse, rename, and verify base game files in NSP and XCI format.",
    },
    "updates": {
        "title":   "UPDATES",
        "emoji":   "🔼",
        "sub":     "VERSION CONTROL",
        "bg":      "#0050A8",
        "bg_h":    "#0077FF",
        "tooltip": "Manage game update patches. Check which versions you have and rename them to match your library.",
    },
    "dlc": {
        "title":   "DLC & ADD-ONS",
        "emoji":   "🎁",
        "sub":     "ADD-ON CONTENT",
        "bg":      "#007A33",
        "bg_h":    "#00B84A",
        "tooltip": "All your downloadable content in one place. Browse and organize add-on files for your Switch library.",
    },
}

MODE_ORDER = ["base", "updates", "dlc"]


class ColorPanel(tk.Frame):
    """Full-height clickable color panel with obvious hover highlight."""

    def __init__(self, parent, mode, cfg, on_select, **kwargs):
        super().__init__(parent, bg=cfg["bg"], cursor=HAND_CURSOR, **kwargs)
        self.mode      = mode
        self.cfg       = cfg
        self.on_select = on_select
        self._bg       = cfg["bg"]
        self._bg_h     = cfg["bg_h"]
        self._bg_widgets   = []   # every widget that needs bg updated
        self._sub_labels   = []   # subtitle labels — fg also changes
        self._build()
        ComicTooltip(self, cfg.get("tooltip", cfg["title"]), accent_color=cfg["bg_h"])

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
        self._reg(tk.Frame(self, bg=self._bg, cursor=HAND_CURSOR)).pack(
            fill="both", expand=True)

        # Centered content block
        c = self._reg(tk.Frame(self, bg=self._bg, cursor=HAND_CURSOR))
        c.pack(fill="x", padx=40)

        self._reg(tk.Label(c, text=self.cfg["emoji"],
                           font=("Arial", 72 + _F * 2),
                           bg=self._bg, cursor=HAND_CURSOR)).pack(anchor="center")

        self._reg(tk.Label(c, text=self.cfg["title"],
                           font=(UI_FONT, 26 + _F, "bold"),
                           fg="#ffffff", bg=self._bg,
                           cursor=HAND_CURSOR)).pack(anchor="center", pady=(22, 0))

        # Subtitle — fg changes on hover for extra clarity
        self._reg(tk.Label(c, text=self.cfg["sub"],
                           font=(UI_FONT, 11 + _F),
                           fg="#aaaaaa", bg=self._bg,
                           cursor=HAND_CURSOR),
                  is_sub=True).pack(anchor="center", pady=(10, 0))

        # Bottom spacer
        self._reg(tk.Frame(self, bg=self._bg, cursor=HAND_CURSOR)).pack(
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


_BAR_BG     = "#151d33"
_BAR_BORDER = "#2a3f5f"


class ModeSelectScreen(tk.Frame):
    """Three full-height Nintendo Switch color panels, exactly equal width."""

    def __init__(self, parent, on_select, logo_img=None, **kwargs):
        super().__init__(parent, bg="#0a0a14", **kwargs)
        self._on_select    = on_select
        self._pre_scan     = tk.BooleanVar(value=self._load_pre_scan())
        self._tooltips     = tk.BooleanVar(value=self._load_tooltips())
        self._cache_after  = None
        _tooltip.set_enabled(self._tooltips.get())
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

        self._build_statusbar()

    # ------------------------------------------------------------------
    # Pre-Scan preference persistence
    # ------------------------------------------------------------------

    def _load_pre_scan(self) -> bool:
        """Load pre_scan setting; default ON when any folder path is cached."""
        try:
            cfg = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                cfg.read(CONFIG_FILE)
                if cfg.has_option("Settings", "pre_scan"):
                    return cfg.getboolean("Settings", "pre_scan")
                # First run — default ON if any folder is already configured
                folders = cfg.options("Folders") if cfg.has_section("Folders") else []
                return any(cfg.get("Folders", k, fallback="") for k in folders)
        except Exception:
            pass
        return True

    def _save_pre_scan(self, value: bool):
        try:
            cfg = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                cfg.read(CONFIG_FILE)
            if "Settings" not in cfg:
                cfg["Settings"] = {}
            cfg["Settings"]["pre_scan"] = str(value).lower()
            with open(CONFIG_FILE, "w") as f:
                cfg.write(f)
        except Exception:
            pass

    def _load_tooltips(self) -> bool:
        try:
            cfg = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                cfg.read(CONFIG_FILE)
                if cfg.has_option("Settings", "tooltips"):
                    return cfg.getboolean("Settings", "tooltips")
        except Exception:
            pass
        return True

    def _save_tooltips(self, value: bool):
        try:
            cfg = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                cfg.read(CONFIG_FILE)
            if "Settings" not in cfg:
                cfg["Settings"] = {}
            cfg["Settings"]["tooltips"] = str(value).lower()
            with open(CONFIG_FILE, "w") as f:
                cfg.write(f)
        except Exception:
            pass

    @property
    def pre_scan_enabled(self) -> bool:
        return self._pre_scan.get()

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=_BAR_BG,
                       highlightthickness=1, highlightbackground=_BAR_BORDER)
        bar.pack(side="bottom", fill="x")

        bar.columnconfigure(0, weight=1)
        bar.columnconfigure(1, weight=0)
        bar.columnconfigure(2, weight=1)

        # Left — hint / sync status
        self._status_lbl = tk.Label(bar, text="Select a mode to get started",
                                    bg=_BAR_BG, fg="#6b7280",
                                    font=(UI_FONT, 9 + _F))
        self._status_lbl.grid(row=0, column=0, sticky="w", padx=(24, 0), pady=10)

        # Center — copyright · version
        tk.Label(bar, text=f"{APP_COPYRIGHT}  ·  v{APP_VERSION}",
                 bg=_BAR_BG, fg="#4b5563",
                 font=(UI_FONT, 8 + _F)).grid(row=0, column=1, pady=10)

        # Right — Pre-Scan toggle · cache timer · sync button
        right = tk.Frame(bar, bg=_BAR_BG)
        right.grid(row=0, column=2, sticky="e", padx=(0, 24), pady=10)

        # Pre-Scan toggle chip
        self._prescan_lbl = tk.Label(right, bg=_BAR_BG, cursor=HAND_CURSOR,
                                     font=(UI_FONT, 8 + _F, "bold"), padx=8, pady=2)
        self._prescan_lbl.pack(side="left", padx=(0, 14))
        self._prescan_lbl.bind("<Button-1>", lambda e: self._toggle_pre_scan())
        self._refresh_prescan_chip()
        ComicTooltip(self._prescan_lbl,
                     "Scans your folders automatically each time the app launches. "
                     "Also re-scans when you enter a mode. Turn off to open instantly "
                     "and browse the last cached results instead.",
                     accent_color="#60a5fa")

        # Tooltips toggle chip
        self._tooltip_lbl = tk.Label(right, bg=_BAR_BG, cursor=HAND_CURSOR,
                                     font=(UI_FONT, 8 + _F, "bold"), padx=8, pady=2)
        self._tooltip_lbl.pack(side="left", padx=(0, 14))
        self._tooltip_lbl.bind("<Button-1>", lambda e: self._toggle_tooltips())
        self._refresh_tooltip_chip()
        ComicTooltip(self._tooltip_lbl,
                     "Show or hide hover tooltips throughout the app. "
                     "Your preference is saved and restored on next launch.",
                     accent_color="#60a5fa")

        # Cache age timer
        self._cache_lbl = tk.Label(right, bg=_BAR_BG, fg="#6b7280",
                                   font=(UI_FONT, 8 + _F))
        self._cache_lbl.pack(side="left", padx=(0, 20))
        self._tick_cache()
        ComicTooltip(self._cache_lbl,
                     "Time since the title database was last synced from the server. "
                     "A fresh database ensures accurate game names and metadata.",
                     accent_color="#6b7280")

        # Sync button
        sync_btn = tk.Label(right, text="🔄 SYNC DATABASE",
                            bg=_BAR_BG, fg="#60a5fa",
                            font=(UI_FONT, 8 + _F, "bold"),
                            cursor=HAND_CURSOR)
        sync_btn.pack(side="left")
        sync_btn.bind("<Button-1>", lambda e: self._sync_db())
        sync_btn.bind("<Enter>",    lambda e: sync_btn.config(fg="#93c5fd"))
        sync_btn.bind("<Leave>",    lambda e: sync_btn.config(fg="#60a5fa"))
        ComicTooltip(sync_btn,
                     "Manually pull the latest title database now. Normally not needed "
                     "since the database auto-updates every 24 hours. Only use this if "
                     "a game released today and you need it immediately.",
                     accent_color="#60a5fa")

    def _refresh_prescan_chip(self):
        on = self._pre_scan.get()
        self._prescan_lbl.config(
            text="⚡ Pre-Scan  ON" if on else "⚡ Pre-Scan  OFF",
            bg="#1e3a5f" if on else "#2a2a3f",
            fg="#60a5fa" if on else "#6b7280",
        )

    def _toggle_pre_scan(self):
        self._pre_scan.set(not self._pre_scan.get())
        self._save_pre_scan(self._pre_scan.get())
        self._refresh_prescan_chip()

    def _refresh_tooltip_chip(self):
        on = self._tooltips.get()
        self._tooltip_lbl.config(
            text="💬 Tooltips  ON" if on else "💬 Tooltips  OFF",
            bg="#1e3a5f" if on else "#2a2a3f",
            fg="#60a5fa" if on else "#6b7280",
        )

    def _toggle_tooltips(self):
        self._tooltips.set(not self._tooltips.get())
        _tooltip.set_enabled(self._tooltips.get())
        self._save_tooltips(self._tooltips.get())
        self._refresh_tooltip_chip()

    def _tick_cache(self):
        """Update the cache age label every 60 seconds."""
        try:
            from db import cache_age_string
            self._cache_lbl.config(text=cache_age_string())
        except Exception:
            self._cache_lbl.config(text="")
        self._cache_after = self.after(60_000, self._tick_cache)

    def _sync_db(self):
        self._status_lbl.config(text="🔄 Syncing database…", fg="#60a5fa")
        self.update_idletasks()
        try:
            from db import load_db, cache_age_string
            load_db(force_refresh=True)
            self._cache_lbl.config(text=cache_age_string())
            self._status_lbl.config(text="✓ Database synced", fg="#10b981")
        except Exception as exc:
            self._status_lbl.config(text=f"❌ Sync failed: {exc}", fg="#ef4444")


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1200x700")

    def _test(mode):
        print(f"Selected: {mode}")

    ModeSelectScreen(root, _test).pack(fill="both", expand=True)
    root.mainloop()
