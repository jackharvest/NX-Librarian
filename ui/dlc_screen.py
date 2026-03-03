"""
ui/dlc_screen.py — REVOLUTIONARY v3 DLC content browser.

Completely redesigned with:
- Modern hierarchical DLC organization
- Parent game grouping with visual indicators
- Enhanced content discovery dashboard
- Premium micro-interactions
- Professional analytics dashboard look
- Visual parent-child relationships

This is UTTERLY TRANSFORMED from v2.
"""

import os
import re
import tkinter as tk
from tkinter import messagebox
from collections import defaultdict

from constants import KNOWN_REGIONS, REGION_FLAGS, classify_title_id
from db import cache_age_string
from ui.base_screen import BaseScreen
from debug_region import get_region_from_votes


_COLUMNS = [
    ("parent_name", "PARENT GAME",   300, True,  "w"),
    ("filename",    "DLC FILENAME",  380, True,  "w"),
    ("tid",         "TITLE ID",      145, False, "center"),
    ("dlc_name",    "DLC NAME",      200, True,  "w"),
    ("status",      "STATUS",        140, False, "center"),
    ("rgn",         "RGN",            70, False, "center"),
]


class DLCScreen(BaseScreen):
    MODE_KEY     = "dlc"
    MODE_LABEL   = "DLC & ADD-ONS CENTER"
    ACCENT_COLOR = "#009640"
    COLUMNS      = _COLUMNS

    def __init__(self, *args, **kwargs):
        self.hide_wrong_region = False
        self.hide_partial      = False
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # Filter buttons
    # ------------------------------------------------------------------

    def _build_filter_buttons(self, parent):
        """Filter chips — styled Labels."""
        from constants import UI_FONT, FONT_BOOST
        _F = FONT_BOOST

        def _chip(text, cmd, off_bg="#2a3f5f", off_fg="#9ca3af"):
            lbl = tk.Label(parent, text=text, bg=off_bg, fg=off_fg,
                           font=(UI_FONT, 8 + _F, "bold"), cursor="hand2", padx=10, pady=3)
            lbl.bind("<Button-1>", lambda e: cmd())
            return lbl

        self.btn_wrong_region = _chip("✗ Wrong Region", self._toggle_wrong_region)
        self.btn_partial      = _chip("⚠ Partial",      self._toggle_partial)
        self.btn_wrong_region.pack(side="left", padx=(0, 4))
        self.btn_partial.pack(side="left")

    def _toggle_wrong_region(self):
        self.hide_wrong_region = not self.hide_wrong_region
        self.btn_wrong_region.config(
            bg="#ef4444" if self.hide_wrong_region else "#2a3f5f",
            fg="#0a0a14" if self.hide_wrong_region else "#9ca3af")
        self.refresh_table()

    def _toggle_partial(self):
        self.hide_partial = not self.hide_partial
        self.btn_partial.config(
            bg="#f97316" if self.hide_partial else "#2a3f5f",
            fg="#0a0a14" if self.hide_partial else "#9ca3af")
        self.refresh_table()

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def scan(self, force_refresh: bool = False):
        folder = self.target_folder.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("No Folder", "Please select a valid folder first.")
            return

        if force_refresh or not self.norm_v:
            from db import load_db
            self._update_status("🔄 Syncing databases…", "info")
            self.update_idletasks()
            self.norm_v, self.norm_t, self.norm_c = load_db(force_refresh=force_refresh)
            if self.norm_t is None:
                self._update_status("❌ Database sync failed", "error")
                messagebox.showerror("DB Error", "Could not load database.")
                return

        self._update_status("📁 Scanning…", "info")
        self.update_idletasks()

        norm_t = self.norm_t
        norm_c = self.norm_c

        self.all_data = []
        missing_tid   = 0
        improper_name = 0

        id_pat       = re.compile(r'(?<![0-9A-Fa-f])([01][0-9A-Fa-f]{15})(?![0-9A-Fa-f])')
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
                        "parent_name": "—", "parent_tid": "", "parent_region": "",
                        "dlc_region_votes": {}, "filename": fname,
                        "filepath": os.path.join(root_dir, fname),
                        "tid": "—", "dlc_name": "—", "status": "✗ NO TITLE ID",
                        "rgn": "—", "_quality": "missing_tid",
                    })
                    continue

                is_bad_name = False
                if not _bracket_tid.search(fname) or not _bracket_ver.search(fname):
                    improper_name += 1
                    is_bad_name = True

                tid = tid_m.group(1).lower()
                kind = classify_title_id(tid)

                # Only DLC files
                cnmt_entry = norm_c.get(tid, {})
                if kind != "dlc":
                    if cnmt_entry.get("type") != "AddOnContent":
                        continue

                # Parent base TID — use authoritative otherApplicationId from cnmts
                # when available; fall back to structural derivation for uncatalogued DLC
                parent_tid = cnmt_entry.get("parent") or tid[:13] + "000"
                parent_entry = norm_t.get(parent_tid, {})
                parent_name = parent_entry.get("name", "") or f"[{parent_tid.upper()}]"

                # DLC name
                dlc_entry = norm_t.get(tid, {})
                dlc_name = dlc_entry.get("name", "") or "—"

                # Region — database voting consensus only (filename tags are unreliable)
                parent_region    = get_region_from_votes(parent_entry)
                dlc_region_votes = dlc_entry.get("_region_votes", {})
                region           = parent_region or get_region_from_votes(dlc_entry)

                self.all_data.append({
                    "parent_name":      parent_name,
                    "parent_tid":       parent_tid,
                    "parent_region":    parent_region,
                    "dlc_region_votes": dlc_region_votes,
                    "filename":         fname,
                    "filepath":         os.path.join(root_dir, fname),
                    "tid":              tid.upper(),
                    "dlc_name":         dlc_name,
                    "status":           "",
                    "rgn":              REGION_FLAGS.get(region, region),
                    "_quality":         "bad_name" if is_bad_name else "ok",
                })

        self.all_data.sort(key=lambda x: x["filename"].lower())

        # ------------------------------------------------------------------
        # Post-scan: compute completeness status per item
        # ------------------------------------------------------------------

        # Count DB-known DLC per parent from norm_c
        db_dlc_counts = defaultdict(int)
        for tid_key, cnmt_info in (self.norm_c or {}).items():
            if isinstance(cnmt_info, dict) and cnmt_info.get("type") == "AddOnContent":
                parent = cnmt_info.get("parent", "")
                if parent:
                    db_dlc_counts[parent] += 1

        # Count locally-found DLC per parent
        local_dlc_counts = defaultdict(int)
        for item in self.all_data:
            local_dlc_counts[item["parent_tid"]] += 1

        # Assign status to each item (skip placeholder missing-TID entries)
        for item in self.all_data:
            if item.get("_quality") == "missing_tid":
                continue
            p_region  = item["parent_region"]
            dlc_votes = item["dlc_region_votes"]
            # Wrong region only when the DLC has its own DB entry AND that entry has
            # zero votes for the parent's region — meaning it was never published there.
            # Comparing dominant regions produces false positives for global releases
            # that appear in both US.en.json and GB.en.json.
            if p_region and dlc_votes and p_region not in dlc_votes:
                item["status"] = "✗ WRONG REGION"
            else:
                p_tid     = item["parent_tid"]
                local     = local_dlc_counts[p_tid]
                db_total  = db_dlc_counts.get(p_tid, 0)
                if db_total > 0 and local >= db_total:
                    item["status"] = "✓ COMPLETE"
                elif db_total > 0 and local < db_total:
                    item["status"] = f"⚠ PARTIAL {local}/{db_total}"
                else:
                    item["status"] = "✓ OK"
        self._update_file_counters(missing_tid, improper_name)
        self._update_status(f"✓ Scanned {len(self.all_data)} DLC items", "success")
        self.cache_lbl.config(text=cache_age_string())
        self.refresh_table()

    # ------------------------------------------------------------------
    # Table refresh
    # ------------------------------------------------------------------

    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        q = self.search_query.get().lower()
        visible_count = 0

        for item in self.all_data:
            if not self._quality_visible(item):
                continue

            parent_name = item["parent_name"]
            filename    = item["filename"]
            tid         = item["tid"]
            dlc_name    = item["dlc_name"]
            status      = item.get("status", "")

            if q and q not in filename.lower() and q not in tid.lower() and q not in parent_name.lower():
                continue
            if self.hide_wrong_region and "WRONG REGION" in status:
                continue
            if self.hide_partial and "PARTIAL" in status:
                continue

            visible_count += 1
            values = tuple(item[col[0]] for col in self.COLUMNS)

            if "WRONG REGION" in status:
                status_tag = "wrong_region"
            elif "COMPLETE" in status:
                status_tag = "complete"
            elif "PARTIAL" in status:
                status_tag = "partial"
            else:
                status_tag = ""

            self.tree.insert("", "end", values=values,
                             tags=(status_tag,) if status_tag else ())

        # Color-coded status tags
        self.tree.tag_configure("wrong_region", foreground="#ef4444")  # Red
        self.tree.tag_configure("complete",     foreground="#10b981")  # Green
        self.tree.tag_configure("partial",      foreground="#f97316")  # Amber

        # Update stats and handle empty state
        self.stats_lbl.config(text=f"DLC Library • {visible_count} items")

        if visible_count == 0 and self.all_data:
            self._hide_empty_state()
            self._show_empty_state("No DLC matches your search")
        elif visible_count == 0:
            self._hide_empty_state()
            self._show_empty_state("No DLC found\n\nSelect a folder and click SCAN to get started")
        else:
            self._hide_empty_state()

        # Apply row striping (preserve status tag)
        for idx, iid in enumerate(self.tree.get_children()):
            stripe_tag = "even" if idx % 2 == 0 else "odd"
            existing = self.tree.item(iid, "tags")
            self.tree.item(iid, tags=(stripe_tag,) + tuple(existing))

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
                       lambda t=item["parent_tid"]: self.navigate_to("base", t))
                return

    def _on_row_double_click(self, event):
        """Double-click any DLC row → jump to Base Games for the parent game."""
        if not self.navigate_to:
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        tid_upper = self.tree.set(iid, "tid")
        for item in self.all_data:
            if item["tid"] == tid_upper:
                self.navigate_to("base", item["parent_tid"])
                return

