"""
ui/updates_screen.py — REVOLUTIONARY v3 updates tracker.

Completely redesigned as a version control dashboard with:
- Visual progress indicators and status cards
- Modern version comparison interface
- Interactive filtering with tag-style chips
- Live update status tracking
- Dynamic color-coded status system
- Premium micro-interactions
- Professional analytics dashboard appearance

This is UTTERLY DIFFERENT from v2.
"""

import os
import re
import tkinter as tk
from tkinter import messagebox
from collections import defaultdict
import time

from constants import KNOWN_REGIONS, REGION_FLAGS, HAND_CURSOR
from db import cache_age_string
from ui.base_screen import BaseScreen
from debug_region import log_region_lookup, clear_log, get_region_from_votes


_COLUMNS = [
    ("filename", "FILENAME",  500, True,  "w"),
    ("tid",      "TITLE ID",  145, False, "center"),
    ("cur_ver",  "CURRENT",    85, False, "center"),
    ("lat_ver",  "LATEST",     85, False, "center"),
    ("cur_int",  "CUR INT",    85, False, "center"),
    ("lat_int",  "LAT INT",    85, False, "center"),
    ("status",   "STATUS",    115, False, "center"),
    ("rgn",      "RGN",        70, False, "center"),
]


class UpdatesScreen(BaseScreen):
    MODE_KEY     = "updates"
    MODE_LABEL   = "VERSION CONTROL CENTER"
    ACCENT_COLOR = "#60a5fa"
    COLUMNS      = _COLUMNS

    def __init__(self, *args, **kwargs):
        self.hide_latest   = False
        self.hide_outdated = False
        self.hide_base     = False
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # Filter buttons — modern chip-style filters
    # ------------------------------------------------------------------

    def _build_filter_buttons(self, parent):
        """Filter chips — styled Labels, no Windows 95 buttons."""
        from constants import UI_FONT, FONT_BOOST
        _F = FONT_BOOST

        def _chip(text, cmd, off_bg="#2a3f5f", off_fg="#9ca3af"):
            lbl = tk.Label(parent, text=text, bg=off_bg, fg=off_fg,
                           font=(UI_FONT, 8 + _F, "bold"), cursor=HAND_CURSOR, padx=10, pady=3)
            lbl.bind("<Button-1>", lambda e: cmd())
            return lbl

        self.btn_latest  = _chip("✓ Latest",    self._toggle_latest)
        self.btn_outdated = _chip("⚠ Old Update", self._toggle_outdated)
        self.btn_base    = _chip("🎮 Base",      self._toggle_base)
        self.btn_latest.pack(side="left", padx=(0, 4))
        self.btn_outdated.pack(side="left", padx=(0, 4))
        self.btn_base.pack(side="left")

    def _toggle_latest(self):
        self.hide_latest = not self.hide_latest
        self.btn_latest.config(
            bg="#60a5fa" if self.hide_latest else "#2a3f5f",
            fg="#0a0a14" if self.hide_latest else "#9ca3af")
        self.refresh_table()

    def _toggle_outdated(self):
        self.hide_outdated = not self.hide_outdated
        self.btn_outdated.config(
            bg="#ef4444" if self.hide_outdated else "#2a3f5f",
            fg="#0a0a14" if self.hide_outdated else "#9ca3af")
        self.refresh_table()

    def _toggle_base(self):
        self.hide_base = not self.hide_base
        self.btn_base.config(
            bg="#06d6d0" if self.hide_base else "#2a3f5f",
            fg="#0a0a14" if self.hide_base else "#9ca3af")
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

        self.all_data = []
        missing_tid   = 0
        improper_name = 0

        id_pat       = re.compile(r'(?<![0-9A-Fa-f])([01][0-9A-Fa-f]{15})(?![0-9A-Fa-f])')
        # [v12345] preferred (v required to avoid matching all-digit TIDs like
        # [0100965017338800]); fallback: bare v12345 not followed by .\d
        # (which would indicate a display version like v1.0.7).
        ver_pat      = re.compile(r'\[v(\d+)\]|[vV](\d+)(?!\.\d)')
        _bracket_tid = re.compile(r'\[([01][0-9A-Fa-f]{15})\]')
        _bracket_ver = re.compile(r'\[v\d+\]', re.IGNORECASE)

        for root_dir, _, files in os.walk(folder):
            for fname in files:
                if not fname.lower().endswith((".nsp", ".xci")):
                    continue

                tid_m = id_pat.search(fname)
                if not tid_m:
                    missing_tid += 1
                    self.all_data.append({
                        "filename": fname, "filepath": os.path.join(root_dir, fname),
                        "tid": "—", "cur_ver": "—", "lat_ver": "—",
                        "cur_int": 0, "lat_int": 0, "status": "✗ NO TITLE ID",
                        "tag": "missing_tid", "mid": "", "rgn": "—",
                        "_quality": "missing_tid",
                    })
                    continue

                is_bad_name = False
                if not _bracket_tid.search(fname) or not _bracket_ver.search(fname):
                    improper_name += 1
                    is_bad_name = True

                tid = tid_m.group(1).lower()
                ver_m = ver_pat.search(fname)
                cur_i = int(ver_m.group(1) or ver_m.group(2)) if ver_m else 0

                # Find version list
                v_list = None
                mid = None
                for sid in [tid, tid[:-3] + "000", tid[:-3] + "800"]:
                    if sid in norm_v:
                        v_list = norm_v[sid]
                        mid = sid
                        break

                # Region detection with database voting consensus
                region = ""
                base_tid = tid[:13] + "000"
                db_entry_base = norm_t.get(base_tid, {})
                db_entry_tid = norm_t.get(tid, {})
                db_entry = db_entry_base or db_entry_tid

                if db_entry:
                    region = get_region_from_votes(db_entry)

                # Check for cross-region mismatch: wrong region only when the update TID has
                # its own DB entry and that entry has ZERO votes for the base game's region.
                # (Many updates appear in multiple regional DBs; dominant-region comparison
                # produces false positives for global releases.)
                base_region  = get_region_from_votes(db_entry_base) if db_entry_base else ""
                update_votes = db_entry_tid.get("_region_votes", {}) if db_entry_tid else {}
                wrong_region = bool(base_region and update_votes and base_region not in update_votes)

                # Log the region lookup for debugging
                log_region_lookup(fname, tid, base_tid, db_entry, "", region)

                # Base game check
                if cur_i == 0:
                    self.all_data.append({
                        "filename": fname,
                        "filepath": os.path.join(root_dir, fname),
                        "tid": tid.upper(),
                        "base_tid": base_tid,
                        "cur_ver": "v0",
                        "lat_ver": "—",
                        "cur_int": 0,
                        "lat_int": 0,
                        "status": "🎮 BASE GAME",
                        "tag": "base",
                        "mid": mid or tid,
                        "rgn": REGION_FLAGS.get(region, region),
                        "_quality": "bad_name" if is_bad_name else "ok",
                    })
                    continue

                # Version comparison
                lat_i = 0
                cur_d = "N/A"
                lat_d = "N/A"
                stat = "Unknown"
                tag = "unknown"

                if v_list:
                    ints = [int(v) for v in (v_list.keys() if isinstance(v_list, dict) else v_list)
                           if str(v).isdigit()]
                    if ints:
                        lat_i = max(ints)
                        cur_d = f"v{cur_i // 65536}.0"
                        lat_d = f"v{lat_i // 65536}.0"
                        if cur_i < lat_i:
                            stat = "⚠ OLD UPDATE"
                            tag = "outdated"
                        else:
                            stat = "✓ LATEST"
                            tag = "latest"

                # Wrong region overrides all other statuses (highest priority)
                if wrong_region:
                    stat = "✗ WRONG REGION"
                    tag = "wrong_region"

                self.all_data.append({
                    "filename": fname,
                    "filepath": os.path.join(root_dir, fname),
                    "tid": tid.upper(),
                    "base_tid": base_tid,
                    "cur_ver": cur_d,
                    "lat_ver": lat_d,
                    "cur_int": cur_i,
                    "lat_int": lat_i,
                    "status": stat,
                    "tag": tag,
                    "mid": mid or tid,
                    "rgn": REGION_FLAGS.get(region, region),
                    "_quality": "bad_name" if is_bad_name else "ok",
                })

        self.all_data.sort(key=lambda x: x["filename"].lower())
        self._update_file_counters(missing_tid, improper_name)
        self._update_status(f"✓ Scanned {len(self.all_data)} items", "success")
        self.cache_lbl.config(text=cache_age_string())
        self.refresh_table()

    # ------------------------------------------------------------------
    # Table refresh
    # ------------------------------------------------------------------

    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        q = self.search_query.get().lower()
        
        visible = 0

        for item in self.all_data:
            if not self._quality_visible(item):
                continue

            fname = item["filename"]
            tid = item["tid"]
            tag = item["tag"]

            if q and q not in fname.lower() and q not in tid.lower():
                continue
            if self.hide_latest and tag == "latest":
                continue
            if self.hide_outdated and tag == "outdated":
                continue
            if self.hide_base and tag == "base":
                continue

            values = tuple(item[col[0]] for col in self.COLUMNS)
            self.tree.insert("", "end", values=values, tags=(tag,))
            visible += 1

        # Color-coded status tags
        self.tree.tag_configure("wrong_region", foreground="#ef4444")  # Red
        self.tree.tag_configure("outdated",     foreground="#f97316")  # Amber
        self.tree.tag_configure("latest",       foreground="#10b981")  # Green
        self.tree.tag_configure("base",         foreground="#60a5fa")  # Blue
        
        # Update stats
        self.stats_lbl.config(text=f"Version Control • {visible}/{len(self.all_data)} items")
        
        # Show empty state if needed
        if visible == 0 and self.all_data:
            self._hide_empty_state()
            self._show_empty_state("No updates match your filters\n\nTry adjusting search or filters")
        elif visible == 0:
            self._hide_empty_state()
            self._show_empty_state("No update files found\n\nSelect a folder and click SCAN to get started")
        else:
            self._hide_empty_state()
        
        # Apply row striping
        for idx, item in enumerate(self.tree.get_children()):
            stripe_tag = "even" if idx % 2 == 0 else "odd"
            existing = self.tree.item(item, "tags")
            self.tree.item(item, tags=(stripe_tag,) + tuple(existing))

        self._schedule_fix_buttons()

    # ------------------------------------------------------------------
    # Cross-screen navigation
    # ------------------------------------------------------------------

    def _add_nav_ctx_items(self, iid, add_fn):
        if not self.navigate_to:
            return
        tid_upper = self.tree.set(iid, "tid")
        for item in self.all_data:
            if item["tid"] == tid_upper:
                fname = item["filename"]
                short = fname[:40] + "…" if len(fname) > 40 else fname
                add_fn(f"🎮 Jump to Base Game for {short}",
                       lambda t=item["base_tid"]: self.navigate_to("base", t))
                return

    def _on_row_double_click(self, event):
        """Double-click any update row → jump to Base Games for that game."""
        if not self.navigate_to:
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        tid_upper = self.tree.set(iid, "tid")
        for item in self.all_data:
            if item["tid"] == tid_upper:
                self.navigate_to("base", item["base_tid"])
                return

