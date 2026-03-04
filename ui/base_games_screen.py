"""
ui/base_games_screen.py — REVOLUTIONARY v3 base games manager.

Completely redesigned with:
- Modern library management dashboard
- Enhanced filtering with chip-style buttons
- Real-time status indicators
- Visual update/DLC presence indicators
- Premium micro-interactions
- Professional analytics dashboard look

This is UTTERLY TRANSFORMED from v2.
"""

import os
import re
import tkinter as tk
from tkinter import messagebox

from constants import KNOWN_REGIONS, REGION_FLAGS, HAND_CURSOR
from db import cache_age_string
from ui.base_screen import BaseScreen
from debug_region import log_region_lookup, clear_log, get_region_from_votes


_COLUMNS = [
    ("filename",     "FILENAME",      560, True,  "w"),
    ("tid",          "TITLE ID",      145, False, "center"),
    ("version",      "VERSION",        80, False, "center"),
    ("release_date", "RELEASE DATE",   105, False, "center"),
    ("has_update",   "UPDATE?",        90, False, "center"),
    ("has_dlc",      "DLC?",           70, False, "center"),
    ("rgn",          "RGN",            70, False, "center"),
]


class BaseGamesScreen(BaseScreen):
    MODE_KEY     = "base"
    MODE_LABEL   = "BASE GAME LIBRARY"
    ACCENT_COLOR = "#ff3b5c"
    COLUMNS      = _COLUMNS

    def __init__(self, *args, **kwargs):
        self.hide_has_update = False
        self.hide_no_update  = False
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # Filter buttons — modern chip-style
    # ------------------------------------------------------------------

    def _build_filter_buttons(self, parent):
        """Filter chips — styled Labels."""
        from constants import UI_FONT, FONT_BOOST
        _F = FONT_BOOST

        def _chip(text, cmd, off_bg="#2a3f5f", off_fg="#9ca3af"):
            lbl = tk.Label(parent, text=text, bg=off_bg, fg=off_fg,
                           font=(UI_FONT, 8 + _F, "bold"), cursor=HAND_CURSOR, padx=10, pady=3)
            lbl.bind("<Button-1>", lambda e: cmd())
            return lbl

        self.btn_has_update = _chip("⬆ Has Update", self._toggle_has_update)
        self.btn_no_update  = _chip("⚠ No Update",  self._toggle_no_update)
        self.btn_has_update.pack(side="left", padx=(0, 4))
        self.btn_no_update.pack(side="left")

    def _toggle_has_update(self):
        self.hide_has_update = not self.hide_has_update
        self.btn_has_update.config(
            bg="#60a5fa" if self.hide_has_update else "#2a3f5f",
            fg="#0a0a14" if self.hide_has_update else "#9ca3af")
        self.refresh_table()

    def _toggle_no_update(self):
        self.hide_no_update = not self.hide_no_update
        self.btn_no_update.config(
            bg="#f97316" if self.hide_no_update else "#2a3f5f",
            fg="#0a0a14" if self.hide_no_update else "#9ca3af")
        self.refresh_table()

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def scan(self, force_refresh: bool = False):
        # Clear previous debug log on fresh scan
        clear_log()
        
        folder = self.target_folder.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("No Folder", "Please select a valid folder first.")
            return

        if force_refresh or not self.norm_v:
            from db import load_db
            self._update_status("🔄 Syncing databases…", "info")
            self.update_idletasks()
            self.norm_v, self.norm_t, self.norm_c = load_db(force_refresh=force_refresh)
            if not self.norm_v:
                self._update_status("❌ Database sync failed", "error")
                messagebox.showerror("DB Error", "Could not load database.")
                return

        self._update_status("📁 Scanning…", "info")
        self.update_idletasks()

        norm_v = self.norm_v
        norm_t = self.norm_t

        self.all_data  = []
        missing_tid    = 0
        improper_name  = 0

        _bracket_tid = re.compile(r'\[([01][0-9A-Fa-f]{15})\]')
        _bracket_ver = re.compile(r'\[v\d+\]', re.IGNORECASE)

        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            if not os.path.isfile(fpath):
                continue
            if not fname.lower().endswith(('.nsp', '.xci')):
                continue

            # Title ID from filename — brackets optional, must start with 0 or 1
            # Uses lookaround to avoid matching substrings of longer hex strings
            match = re.search(r'(?<![0-9A-Fa-f])([01][0-9A-Fa-f]{15})(?![0-9A-Fa-f])', fname)
            if not match:
                missing_tid += 1
                self.all_data.append({
                    "filename": fname, "filepath": fpath, "tid": "—", "version": "—",
                    "release_date": "—", "has_update": "—", "has_dlc": "—",
                    "rgn": "—", "_quality": "missing_tid",
                })
                continue

            # Strictly named = TID in brackets AND version in brackets
            is_bad_name = False
            if not _bracket_tid.search(fname) or not _bracket_ver.search(fname):
                improper_name += 1
                is_bad_name = True

            tid = match.group(1).lower()       # lowercase for all DB lookups
            base_tid = tid[:13] + "000"

            # Version
            version = 0
            try:
                v_match = re.search(r'\[v(\d+)\]', fname, re.IGNORECASE)
                if v_match:
                    version = int(v_match.group(1))
            except Exception:
                pass

            # Region — database voting consensus (norm_t keys are lowercase)
            region = ""
            db_entry = norm_t.get(tid) or norm_t.get(base_tid) or {}
            
            if db_entry:
                region = get_region_from_votes(db_entry)

            # Log the region lookup for debugging
            log_region_lookup(fname, tid, base_tid, db_entry, "", region)
            if not region:
                region = "—"

            # Release date
            release_date = str(db_entry.get("releaseDate", "") or "—")
            if len(release_date) == 8 and release_date.isdigit():
                release_date = f"{release_date[:4]}-{release_date[4:6]}-{release_date[6:]}"

            # Does an update exist?
            update_tid = base_tid[:-3] + "800"
            v_list = norm_v.get(update_tid) or norm_v.get(base_tid)
            has_update_flag = False
            if v_list:
                ints = [int(v) for v in (v_list.keys() if isinstance(v_list, dict) else v_list)
                       if str(v).isdigit()]
                has_update_flag = bool(ints)

            update_str = "✓ Released" if has_update_flag else "—"

            # DLC?
            has_dlc_flag = False
            for dlc_tid in norm_t.keys():
                if dlc_tid.startswith(base_tid[:13]):
                    has_dlc_flag = True
                    break
            dlc_str = "✓ Released" if has_dlc_flag else "—"

            self.all_data.append({
                "filename":     fname,
                "filepath":     fpath,
                "tid":          tid.upper(),
                "version":      version,
                "release_date": release_date,
                "has_update":   update_str,
                "has_dlc":      dlc_str,
                "rgn":          REGION_FLAGS.get(region, region),
                "_quality":     "bad_name" if is_bad_name else "ok",
            })

        self.all_data.sort(key=lambda x: x["filename"].lower())
        self._update_file_counters(missing_tid, improper_name)
        self._update_status(f"✓ Scanned {len(self.all_data)} base games", "success")
        self.cache_lbl.config(text=cache_age_string())
        self.refresh_table()

    def refresh_table(self):
        """Filter and display table with professional empty states."""
        self.tree.delete(*self.tree.get_children())
        
        # Count visible items
        visible = 0
        
        for row in self.all_data:
            if not self._quality_visible(row):
                continue

            # Filter by search
            search_term = self.search_query.get().lower()
            if search_term and search_term not in row["filename"].lower():
                continue

            # Filter by toggle
            if self.hide_has_update and "Released" in row["has_update"]:
                continue
            if self.hide_no_update and row["has_update"] == "—":
                continue

            # Insert row
            values = tuple(row[col[0]] for col in self.COLUMNS)
            self.tree.insert("", "end", values=values)
            visible += 1
        
        # Update stats
        self.stats_lbl.config(text=f"Library • {visible}/{len(self.all_data)} items")
        
        # Show empty state if needed
        if visible == 0 and self.all_data:
            self._hide_empty_state()
            self._show_empty_state("No games match your filters\n\nTry adjusting search or filters")
        elif visible == 0:
            self._hide_empty_state()
            self._show_empty_state("No games found in library\n\nSelect a folder and click SCAN to get started")
        else:
            self._hide_empty_state()
        
        # Apply row striping
        for idx, item in enumerate(self.tree.get_children()):
            stripe_tag = "even" if idx % 2 == 0 else "odd"
            self.tree.item(item, tags=(stripe_tag,))

        self._schedule_fix_buttons()

    # ------------------------------------------------------------------
    # Cross-screen navigation
    # ------------------------------------------------------------------

    def _nav_col_key(self, event):
        """Return column key under the cursor, or None if not a nav column."""
        if self.tree.identify("region", event.x, event.y) != "cell":
            return None
        col = self.tree.identify_column(event.x)
        try:
            return self.COLUMNS[int(col[1:]) - 1][0]
        except IndexError:
            return None

    def _on_tree_motion(self, event):
        col_key = self._nav_col_key(event)
        iid = self.tree.identify_row(event.y)
        if not iid or col_key not in ("has_update", "has_dlc"):
            self.tree.config(cursor="")
            return
        val = self.tree.set(iid, col_key)
        self.tree.config(cursor=HAND_CURSOR if val and val != "—" else "")

    def _on_row_click(self, event):
        """Single-click UPDATE? / DLC? cells → navigate."""
        if not self.navigate_to:
            return
        col_key = self._nav_col_key(event)
        if col_key not in ("has_update", "has_dlc"):
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        val = self.tree.set(iid, col_key)
        if not val or val == "—":
            return
        tid = self.tree.set(iid, "tid").lower()
        if col_key == "has_update":
            self.navigate_to("updates", tid)
        elif col_key == "has_dlc":
            self.navigate_to("dlc", tid)

    def _on_row_double_click(self, event):
        """Double-click also navigates (same as single-click for these columns)."""
        self._on_row_click(event)

    def _add_nav_ctx_items(self, iid, add_fn):
        if not self.navigate_to:
            return
        tid = self.tree.set(iid, "tid").lower()
        has_update = self.tree.set(iid, "has_update")
        has_dlc    = self.tree.set(iid, "has_dlc")
        fname      = self.tree.set(iid, "filename")
        short      = fname[:40] + "…" if len(fname) > 40 else fname
        if has_update and has_update != "—":
            add_fn(f"⬆  Show Update for {short}",
                   lambda t=tid: self.navigate_to("updates", t))
        if has_dlc and has_dlc != "—":
            add_fn(f"🎮 Show DLC for {short}",
                   lambda t=tid: self.navigate_to("dlc", t))
