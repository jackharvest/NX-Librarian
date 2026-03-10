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


# ---------------------------------------------------------------------------
# Panel configuration
# ---------------------------------------------------------------------------

PANEL_CONFIG = {
    "base": {
        "title":   "BASE GAMES",
        "sub":     "NSP  ·  XCI",
        "neon":    "#ff2244",
        "tooltip": "Your main game archive. Browse, rename, and verify base game files in NSP and XCI format.",
    },
    "updates": {
        "title":   "UPDATES",
        "sub":     "VERSION CONTROL",
        "neon":    "#00aaff",
        "tooltip": "Manage game update patches. Check which versions you have and rename them to match your library.",
    },
    "dlc": {
        "title":   "DLC & ADD-ONS",
        "sub":     "ADD-ON CONTENT",
        "neon":    "#00ee77",
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

    def _hover_start(self):
        self._hovered = True
        self._cancel_anim()
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

        # ── Neon icon ─────────────────────────────────────────────────
        icon_cy = cy - 68
        if self.mode == "base":
            self._icon_controller(cx, icon_cy, neon, glow_col)
        elif self.mode == "updates":
            self._icon_update(cx, icon_cy, neon, glow_col)
        else:
            self._icon_gift(cx, icon_cy, neon, glow_col)

        # ── Title with glow shadow ────────────────────────────────────
        title_y   = cy + 32
        title_fnt = (UI_FONT, 28 + _F, "bold")
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            self.create_text(cx + dx, title_y + dy,
                             text=cfg["title"], font=title_fnt,
                             fill=glow_col, anchor="center")
        self.create_text(cx, title_y,
                         text=cfg["title"], font=title_fnt,
                         fill=neon, anchor="center")

        # ── Subtitle ─────────────────────────────────────────────────
        self.create_text(cx, cy + 70,
                         text=cfg["sub"],
                         font=(UI_FONT, 11 + _F),
                         fill=sub_col, anchor="center")

    # ------------------------------------------------------------------
    # Icon drawing helpers
    # ------------------------------------------------------------------

    def _rrect(self, x1, y1, x2, y2, r, color, lw):
        """Rounded-rectangle outline."""
        kw = dict(outline=color, width=lw, style="arc")
        self.create_arc(x1,       y1,       x1+2*r, y1+2*r, start=90,  extent=90, **kw)
        self.create_arc(x2-2*r,   y1,       x2,     y1+2*r, start=0,   extent=90, **kw)
        self.create_arc(x2-2*r,   y2-2*r,   x2,     y2,     start=270, extent=90, **kw)
        self.create_arc(x1,       y2-2*r,   x1+2*r, y2,     start=180, extent=90, **kw)
        self.create_line(x1+r, y1, x2-r, y1, fill=color, width=lw)
        self.create_line(x2, y1+r, x2, y2-r, fill=color, width=lw)
        self.create_line(x1+r, y2, x2-r, y2, fill=color, width=lw)
        self.create_line(x1, y1+r, x1, y2-r, fill=color, width=lw)

    def _stroke(self, draw_fn, neon, glow):
        """Draw twice: thick dim glow behind, thin bright on top."""
        draw_fn(glow, 6)
        draw_fn(neon, 2)

    # ── Controller ────────────────────────────────────────────────────

    def _icon_controller(self, cx, cy, neon, glow):
        def body(col, lw):
            self._rrect(cx-42, cy-20, cx+42, cy+20, 10, col, lw)

        def left_grip(col, lw):
            self.create_arc(cx-42, cy+8, cx-14, cy+44,
                            start=0, extent=180, outline=col, width=lw, style="arc")

        def right_grip(col, lw):
            self.create_arc(cx+14, cy+8, cx+42, cy+44,
                            start=0, extent=180, outline=col, width=lw, style="arc")

        def left_stick(col, lw):
            self.create_oval(cx-30, cy-13, cx-14, cy+3, outline=col, width=lw)

        def dpad(col, lw):
            dpx, dpy, s = cx-8, cy+10, 8
            self.create_line(dpx-s, dpy, dpx+s, dpy, fill=col, width=lw)
            self.create_line(dpx, dpy-s, dpx, dpy+s, fill=col, width=lw)

        def right_stick(col, lw):
            self.create_oval(cx+14, cy, cx+30, cy+16, outline=col, width=lw)

        def buttons(col, lw):
            for bx, by in [(cx+30, cy-8), (cx+22, cy-16), (cx+22, cy), (cx+14, cy-8)]:
                self.create_oval(bx-4, by-4, bx+4, by+4, outline=col, width=lw)

        for fn in (body, left_grip, right_grip, left_stick, dpad, right_stick, buttons):
            self._stroke(fn, neon, glow)

    # ── Update / triangle-in-rounded-square ───────────────────────────

    def _icon_update(self, cx, cy, neon, glow):
        def square(col, lw):
            self._rrect(cx-38, cy-38, cx+38, cy+38, 12, col, lw)

        def triangle(col, lw):
            pts = [cx, cy-20,  cx+22, cy+16,  cx-22, cy+16]
            self.create_polygon(*pts, outline=col, fill="", width=lw)

        for fn in (square, triangle):
            self._stroke(fn, neon, glow)

    # ── Gift box ──────────────────────────────────────────────────────

    def _icon_gift(self, cx, cy, neon, glow):
        lid_top  = cy - 44
        lid_bot  = cy - 28
        box_bot  = cy + 32

        def box(col, lw):
            self.create_rectangle(cx-32, lid_bot, cx+32, box_bot,
                                   outline=col, width=lw, fill="")

        def lid(col, lw):
            self.create_rectangle(cx-36, lid_top, cx+36, lid_bot,
                                   outline=col, width=lw, fill="")

        def ribbons(col, lw):
            # vertical ribbon
            self.create_line(cx, lid_top, cx, box_bot, fill=col, width=lw)
            # horizontal ribbon at lid joint
            self.create_line(cx-36, lid_bot, cx+36, lid_bot, fill=col, width=lw)

        def bow(col, lw):
            # Left loop
            self.create_arc(cx-28, lid_top-22, cx+2, lid_top+4,
                            start=0, extent=270, outline=col, width=lw, style="arc")
            # Right loop
            self.create_arc(cx-2, lid_top-22, cx+28, lid_top+4,
                            start=270, extent=270, outline=col, width=lw, style="arc")

        for fn in (box, lid, ribbons, bow):
            self._stroke(fn, neon, glow)


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

        for idx, mode in enumerate(MODE_ORDER):
            panel = GlowPanel(container, mode, PANEL_CONFIG[mode], self._on_select)
            panel.grid(row=0, column=idx, sticky="nsew",
                       padx=(0, 1) if idx < len(MODE_ORDER) - 1 else 0)

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
