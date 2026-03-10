"""
ui/mode_select.py — Mode selection screen.

Three Canvas panels on a pure black background.  Each panel draws its
own neon-outline icon (canvas primitives), glowing title/subtitle text,
and an animated spotlight that sweeps down from the top on hover.
"""

import configparser
import os
import tkinter as tk
from constants import UI_FONT, FONT_BOOST, HAND_CURSOR, APP_VERSION, APP_COPYRIGHT, CONFIG_FILE
from ui.tooltip import ComicTooltip
import ui.tooltip as _tooltip

_F = FONT_BOOST

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _dim(hex_color, factor):
    r, g, b = _hex_to_rgb(hex_color)
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


def _lighten(hex_color, factor):
    """Blend hex_color toward white by factor (0=unchanged, 1=white)."""
    r, g, b = _hex_to_rgb(hex_color)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------------------
# Panel configuration
# ---------------------------------------------------------------------------

PANEL_CONFIG = {
    "base": {
        "title":   "BASE GAMES",
        "sub":     "NSP  ·  XCI",
        "neon":    "#ff2244",
        "icon":    "🎮",
        "tooltip": "Your main game archive. Browse, rename, and verify base game files in NSP and XCI format.",
    },
    "updates": {
        "title":   "UPDATES",
        "sub":     "VERSION CONTROL",
        "neon":    "#00aaff",
        "icon":    "🔄",
        "tooltip": "Manage game update patches. Check which versions you have and rename them to match your library.",
    },
    "dlc": {
        "title":   "DLC & ADD-ONS",
        "sub":     "ADD-ON CONTENT",
        "neon":    "#00ee77",
        "icon":    "🎁",
        "tooltip": "All your downloadable content in one place. Browse and organize add-on files for your Switch library.",
    },
}

MODE_ORDER = ["base", "updates", "dlc"]

# Spotlight animation
_ANIM_FRAMES   = 14
_ANIM_STEP_MS  = 14
_SPOTLIGHT_MAX = 0.54   # fraction of panel height


# ---------------------------------------------------------------------------
# GlowPanel
# ---------------------------------------------------------------------------

class GlowPanel(tk.Canvas):
    """
    Full-height neon panel.  Black background.  On hover a spotlight of the
    panel's neon color sweeps down from the top and stops halfway.
    Neon outline icons are drawn with canvas primitives (glow = wide dim
    stroke behind a narrow bright stroke).
    """

    def __init__(self, parent, mode, cfg, on_select, **kwargs):
        super().__init__(parent, bg="#000000",
                         highlightthickness=0, bd=0,
                         cursor=HAND_CURSOR, **kwargs)
        self.mode      = mode
        self.cfg       = cfg
        self.on_select = on_select
        self._hovered  = False
        self._spot     = 0.0   # current spotlight fraction (0–_SPOTLIGHT_MAX)
        self._anim_id  = None

        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Button-1>",  lambda e: on_select(mode))
        self.bind("<Enter>",     lambda e: self._hover_start())
        self.bind("<Leave>",     lambda e: self._hover_leave(e))

        ComicTooltip(self, cfg.get("tooltip", cfg["title"]),
                     accent_color=cfg["neon"])

    # ------------------------------------------------------------------
    # Hover / animation
    # ------------------------------------------------------------------

    def _clear_spotlight(self):
        """Immediately extinguish spotlight — called by siblings on hover."""
        self._hovered = False
        self._cancel_anim()
        self._spot = 0.0
        self._redraw()

    def _hover_start(self):
        self._hovered = True
        self._cancel_anim()
        # Force siblings to clear so a stuck spotlight can't linger
        for sib in getattr(self, "_siblings", []):
            sib._clear_spotlight()
        self._animate()

    def _hover_leave(self, event):
        try:
            if (self.winfo_rootx() <= event.x_root <= self.winfo_rootx() + self.winfo_width() and
                    self.winfo_rooty() <= event.y_root <= self.winfo_rooty() + self.winfo_height()):
                return
        except Exception:
            pass
        self._hovered = False
        self._cancel_anim()
        self._spot = 0.0
        self._redraw()

    def _animate(self):
        # Sticky hover fix: verify cursor is still inside this widget
        try:
            mx = self.winfo_pointerx() - self.winfo_rootx()
            my = self.winfo_pointery() - self.winfo_rooty()
            if not (0 <= mx < self.winfo_width() and 0 <= my < self.winfo_height()):
                self._hovered = False
        except Exception:
            pass

        if not self._hovered:
            self._spot = 0.0
            self._redraw()
            return

        step = _SPOTLIGHT_MAX / _ANIM_FRAMES
        self._spot = min(self._spot + step, _SPOTLIGHT_MAX)
        self._redraw()
        if self._spot < _SPOTLIGHT_MAX:
            self._anim_id = self.after(_ANIM_STEP_MS, self._animate)

    def _cancel_anim(self):
        if self._anim_id:
            self.after_cancel(self._anim_id)
            self._anim_id = None

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 4 or h < 4:
            return

        cx  = w // 2
        cy  = h // 2
        cfg = self.cfg
        neon     = cfg["neon"]
        glow_col = _dim(neon, 0.35)
        sub_col  = _dim(neon, 0.70)

        # ── Spotlight from top ────────────────────────────────────────
        if self._spot > 0:
            sh = int(self._spot * h)
            nr, ng, nb = _hex_to_rgb(neon)
            stripe = 4
            for y in range(0, sh, stripe):
                t = 1.0 - y / sh
                t = t * t              # quadratic: fast at top, tapers off
                intensity = 0.28 * t
                r = int(nr * intensity)
                g = int(ng * intensity)
                b = int(nb * intensity)
                y2 = min(y + stripe, sh)
                self.create_rectangle(0, y, w, y2,
                                      fill=f"#{r:02x}{g:02x}{b:02x}",
                                      outline="")

        # ── Neon icon (emoji with glow) ───────────────────────────────
        icon_y   = cy - 60
        icon_fnt = (UI_FONT, 54)
        for dist, factor in ((8, 0.15), (5, 0.28), (3, 0.45), (1, 0.65)):
            gc = _dim(neon, factor)
            for dx, dy in ((-dist, 0), (dist, 0), (0, -dist), (0, dist),
                           (-dist, -dist), (dist, -dist), (-dist, dist), (dist, dist)):
                self.create_text(cx + dx, icon_y + dy,
                                 text=cfg["icon"], font=icon_fnt,
                                 fill=gc, anchor="center")
        self.create_text(cx, icon_y, text=cfg["icon"], font=icon_fnt,
                         fill=_lighten(neon, 0.82), anchor="center")

        # ── Title with multi-layer neon glow ─────────────────────────
        title_y   = cy + 32
        title_fnt = (UI_FONT, 28 + _F, "bold")
        # Outer → inner glow rings: larger offset = dimmer, smaller = brighter
        for dist, factor in ((6, 0.18), (4, 0.28), (2, 0.45), (1, 0.65)):
            gc = _dim(neon, factor)
            for dx, dy in ((-dist, 0), (dist, 0), (0, -dist), (0, dist),
                           (-dist, -dist), (dist, -dist), (-dist, dist), (dist, dist)):
                self.create_text(cx + dx, title_y + dy,
                                 text=cfg["title"], font=title_fnt,
                                 fill=gc, anchor="center")
        # Near-white neon core
        self.create_text(cx, title_y,
                         text=cfg["title"], font=title_fnt,
                         fill=_lighten(neon, 0.82), anchor="center")

        # ── Subtitle with glow ────────────────────────────────────────
        sub_y = cy + 88
        for dist, factor in ((3, 0.22), (2, 0.40), (1, 0.60)):
            gc = _dim(neon, factor)
            for dx, dy in ((-dist, 0), (dist, 0), (0, -dist), (0, dist)):
                self.create_text(cx + dx, sub_y + dy,
                                 text=cfg["sub"],
                                 font=(UI_FONT, 11 + _F),
                                 fill=gc, anchor="center")
        self.create_text(cx, sub_y,
                         text=cfg["sub"],
                         font=(UI_FONT, 11 + _F),
                         fill=_lighten(neon, 0.72), anchor="center")



# ---------------------------------------------------------------------------
# Status-bar constants
# ---------------------------------------------------------------------------

_BAR_BG     = "#0a0f1a"
_BAR_BORDER = "#1a2535"


# ---------------------------------------------------------------------------
# ModeSelectScreen
# ---------------------------------------------------------------------------

class ModeSelectScreen(tk.Frame):
    """Three full-height neon panels, exactly equal width."""

    def __init__(self, parent, on_select, logo_img=None, **kwargs):
        super().__init__(parent, bg="#000000", **kwargs)
        self._on_select   = on_select
        self._pre_scan    = tk.BooleanVar(value=self._load_pre_scan())
        self._tooltips    = tk.BooleanVar(value=self._load_tooltips())
        self._cache_after = None
        _tooltip.set_enabled(self._tooltips.get())
        self._build()

    def _build(self):
        container = tk.Frame(self, bg="#111111")
        container.pack(fill="both", expand=True)

        for i in range(3):
            container.columnconfigure(i, weight=1, uniform="panels")
        container.rowconfigure(0, weight=1)

        panels = []
        for idx, mode in enumerate(MODE_ORDER):
            panel = GlowPanel(container, mode, PANEL_CONFIG[mode], self._on_select)
            panel.grid(row=0, column=idx, sticky="nsew",
                       padx=(0, 1) if idx < len(MODE_ORDER) - 1 else 0)
            panels.append(panel)

        for i, panel in enumerate(panels):
            panel._siblings = [p for j, p in enumerate(panels) if j != i]

        self._build_statusbar()

    # ------------------------------------------------------------------
    # Preference persistence (unchanged)
    # ------------------------------------------------------------------

    def _load_pre_scan(self) -> bool:
        try:
            cfg = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                cfg.read(CONFIG_FILE)
                if cfg.has_option("Settings", "pre_scan"):
                    return cfg.getboolean("Settings", "pre_scan")
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

        self._status_lbl = tk.Label(bar, text="Select a mode to get started",
                                    bg=_BAR_BG, fg="#6b7280",
                                    font=(UI_FONT, 9 + _F))
        self._status_lbl.grid(row=0, column=0, sticky="w", padx=(24, 0), pady=10)

        tk.Label(bar, text=f"{APP_COPYRIGHT}  ·  v{APP_VERSION}",
                 bg=_BAR_BG, fg="#3d4a5c",
                 font=(UI_FONT, 8 + _F)).grid(row=0, column=1, pady=10)

        right = tk.Frame(bar, bg=_BAR_BG)
        right.grid(row=0, column=2, sticky="e", padx=(0, 24), pady=10)

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

        self._tooltip_lbl = tk.Label(right, bg=_BAR_BG, cursor=HAND_CURSOR,
                                     font=(UI_FONT, 8 + _F, "bold"), padx=8, pady=2)
        self._tooltip_lbl.pack(side="left", padx=(0, 14))
        self._tooltip_lbl.bind("<Button-1>", lambda e: self._toggle_tooltips())
        self._refresh_tooltip_chip()
        ComicTooltip(self._tooltip_lbl,
                     "Show or hide hover tooltips throughout the app. "
                     "Your preference is saved and restored on next launch.",
                     accent_color="#60a5fa")

        self._cache_lbl = tk.Label(right, bg=_BAR_BG, fg="#6b7280",
                                   font=(UI_FONT, 8 + _F))
        self._cache_lbl.pack(side="left", padx=(0, 20))
        self._tick_cache()
        ComicTooltip(self._cache_lbl,
                     "Time since the title database was last synced from the server. "
                     "A fresh database ensures accurate game names and metadata.",
                     accent_color="#6b7280")

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
            bg="#152240" if on else "#1a1a2a",
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
            bg="#152240" if on else "#1a1a2a",
            fg="#60a5fa" if on else "#6b7280",
        )

    def _toggle_tooltips(self):
        self._tooltips.set(not self._tooltips.get())
        _tooltip.set_enabled(self._tooltips.get())
        self._save_tooltips(self._tooltips.get())
        self._refresh_tooltip_chip()

    def _tick_cache(self):
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
