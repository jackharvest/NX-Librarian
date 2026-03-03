"""
ui/updates_screen.py — Premium v3 updates mode.

Scans update files and compares against version database.
Updated to work with the new sophisticated base_screen design system.
"""

import os
import re
import tkinter as tk
from tkinter import messagebox
from collections import defaultdict

from constants import KNOWN_REGIONS, REGION_FLAGS
from db import cache_age_string
from ui.base_screen import BaseScreen


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
    MODE_LABEL   = "UPDATES LIBRARY"
    ACCENT_COLOR = "#4a90e2"
    COLUMNS      = _COLUMNS

    def __init__(self, *args, **kwargs):
        self.hide_latest   = False
        self.hide_outdated = False
        self.hide_base     = False
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # Filter buttons
    # ------------------------------------------------------------------

    def _build_filter_buttons(self, parent):
        self.btn_latest = tk.Button(parent, text="Hide Latest",
                                    command=self._toggle_latest,
                                    bg="#2a2a3e", relief="flat", width=12, cursor="hand2",
                                    fg="#b0b0c8", activebackground="#00a7d8", activeforeground="#0f0f1e",
                                    font=("Segoe UI", 8, "bold"))
        self.btn_latest.pack(side="left", padx=(16, 0))

        self.btn_outdated = tk.Button(parent, text="Hide Outdated",
                                      command=self._toggle_outdated,
                                      bg="#2a2a3e", relief="flat", width=16, cursor="hand2",
                                      fg="#b0b0c8", activebackground="#e74c55", activeforeground="#0f0f1e",
                                      font=("Segoe UI", 8, "bold"))
        self.btn_outdated.pack(side="left", padx=(8, 0))

        self.btn_base = tk.Button(parent, text="Hide Base",
                                  command=self._toggle_base,
                                  bg="#2a2a3e", relief="flat", width=10, cursor="hand2",
                                  fg="#b0b0c8", activebackground="#1dd1a1", activeforeground="#0f0f1e",
                                  font=("Segoe UI", 8, "bold"))
        self.btn_base.pack(side="left", padx=(8, 0))

    def _toggle_latest(self):
        self.hide_latest = not self.hide_latest
        self.btn_latest.config(bg="#00a7d8" if self.hide_latest else "#2a2a3e",
                              fg="#0f0f1e" if self.hide_latest else "#b0b0c8")
        self.refresh_table()

    def _toggle_outdated(self):
        self.hide_outdated = not self.hide_outdated
        self.btn_outdated.config(bg="#e74c55" if self.hide_outdated else "#2a2a3e",
                                fg="#0f0f1e" if self.hide_outdated else "#b0b0c8")
        self.refresh_table()

    def _toggle_base(self):
        self.hide_base = not self.hide_base
        self.btn_base.config(bg="#1dd1a1" if self.hide_base else "#2a2a3e",
                            fg="#0f0f1e" if self.hide_base else "#b0b0c8")
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
            self.status_lbl.config(text="Syncing databases…")
            self.update_idletasks()
            self.norm_v, self.norm_t, self.norm_c = load_db(force_refresh=force_refresh)
            if not self.norm_v:
                messagebox.showerror("DB Error", "Could not load database.")
                return

        self.status_lbl.config(text="Scanning…")
        self.update_idletasks()

        norm_v = self.norm_v
        norm_t = self.norm_t

        self.all_data = []

        id_pat = re.compile(r'\[([01][0-9A-Fa-f]{15})\]')
        ver_pat = re.compile(r'\[v?(\d+)\]')

        for root_dir, _, files in os.walk(folder):
            for fname in files:
                if not fname.lower().endswith((".nsp", ".xci")):
                    continue

                tid_m = id_pat.search(fname)
                if not tid_m:
                    continue

                tid = tid_m.group(1).lower()
                ver_m = ver_pat.search(fname)
                cur_i = int(ver_m.group(1)) if ver_m else 0

                # Find version list
                v_list = None
                mid = None
                for sid in [tid, tid[:-3] + "000", tid[:-3] + "800"]:
                    if sid in norm_v:
                        v_list = norm_v[sid]
                        mid = sid
                        break

                # Region
                region = ""
                if mid:
                    region = norm_t.get(mid, {}).get("_region", "")
                if not region:
                    for token in re.findall(r'\[([^\]]+)\]', fname):
                        if token.upper() in KNOWN_REGIONS:
                            region = token.upper()
                            break

                # Base game check
                if cur_i == 0:
                    self.all_data.append({
                        "filename": fname,
                        "tid": tid.upper(),
                        "cur_ver": "v0",
                        "lat_ver": "—",
                        "cur_int": 0,
                        "lat_int": 0,
                        "status": "🎮 BASE GAME",
                        "tag": "base",
                        "mid": mid or tid,
                        "rgn": REGION_FLAGS.get(region, region),
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
                            stat = "⚠ OUTDATED"
                            tag = "outdated"
                        else:
                            stat = "✓ LATEST"
                            tag = "latest"

                self.all_data.append({
                    "filename": fname,
                    "tid": tid.upper(),
                    "cur_ver": cur_d,
                    "lat_ver": lat_d,
                    "cur_int": cur_i,
                    "lat_int": lat_i,
                    "status": stat,
                    "tag": tag,
                    "mid": mid or tid,
                    "rgn": REGION_FLAGS.get(region, region),
                })

        self.status_lbl.config(text=f"Found {len(self.all_data)} items")
        self.cache_lbl.config(text=cache_age_string())
        self.refresh_table()

    # ------------------------------------------------------------------
    # Table refresh
    # ------------------------------------------------------------------

    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        q = self.search_query.get().lower()

        for item in self.all_data:
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

        self.tree.tag_configure("outdated", foreground="#e74c55")
        self.tree.tag_configure("latest", foreground="#1dd1a1")
        self.tree.tag_configure("base", foreground="#4a90e2")
