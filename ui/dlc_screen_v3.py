"""
ui/dlc_screen.py — Premium v3 DLC mode.

Scans for DLC files and groups by parent game.
Updated to work with the new sophisticated base_screen design system.
"""

import os
import re
import tkinter as tk
from tkinter import messagebox
from collections import defaultdict

from constants import KNOWN_REGIONS, REGION_FLAGS, classify_title_id
from db import cache_age_string
from ui.base_screen import BaseScreen


_COLUMNS = [
    ("parent_name", "PARENT GAME",   320, True,  "w"),
    ("filename",    "DLC FILENAME",  400, True,  "w"),
    ("tid",         "TITLE ID",      145, False, "center"),
    ("dlc_name",    "DLC NAME",      220, True,  "w"),
    ("rgn",         "RGN",            70, False, "center"),
]


class DLCScreen(BaseScreen):
    MODE_KEY     = "dlc"
    MODE_LABEL   = "DLC LIBRARY"
    ACCENT_COLOR = "#1dd1a1"
    COLUMNS      = _COLUMNS

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
            if self.norm_t is None:
                messagebox.showerror("DB Error", "Could not load database.")
                return

        self.status_lbl.config(text="Scanning…")
        self.update_idletasks()

        norm_t = self.norm_t
        norm_c = self.norm_c

        self.all_data = []
        id_pat = re.compile(r'\[([01][0-9A-Fa-f]{15})\]')

        for root_dir, _, files in os.walk(folder):
            for fname in files:
                if not fname.lower().endswith((".nsp", ".xci")):
                    continue

                tid_m = id_pat.search(fname)
                if not tid_m:
                    continue

                tid = tid_m.group(1).lower()
                kind = classify_title_id(tid)

                # Only DLC files
                if kind != "dlc":
                    cnmt_type = norm_c.get(tid, "")
                    if cnmt_type != "AddOnContent":
                        continue

                # Parent base TID
                parent_tid = tid[:12] + "0000"
                parent_entry = norm_t.get(parent_tid, {})
                parent_name = parent_entry.get("name", "") or f"[{parent_tid.upper()}]"

                # DLC name
                dlc_entry = norm_t.get(tid, {})
                dlc_name = dlc_entry.get("name", "") or "—"

                # Region
                region = parent_entry.get("_region", "")
                if not region:
                    region = dlc_entry.get("_region", "")
                if not region:
                    for token in re.findall(r'\[([^\]]+)\]', fname):
                        if token.upper() in KNOWN_REGIONS:
                            region = token.upper()
                            break

                self.all_data.append({
                    "parent_name": parent_name,
                    "filename": fname,
                    "tid": tid.upper(),
                    "dlc_name": dlc_name,
                    "rgn": REGION_FLAGS.get(region, region),
                })

        self.all_data.sort(key=lambda x: (x["parent_name"], x["filename"]))
        self.status_lbl.config(text=f"Found {len(self.all_data)} DLC files")
        self.cache_lbl.config(text=cache_age_string())
        self.refresh_table()

    # ------------------------------------------------------------------
    # Table refresh
    # ------------------------------------------------------------------

    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        q = self.search_query.get().lower()

        for item in self.all_data:
            parent_name = item["parent_name"]
            filename = item["filename"]
            tid = item["tid"]
            dlc_name = item["dlc_name"]

            if q and q not in filename.lower() and q not in tid.lower() and q not in parent_name.lower():
                continue

            values = tuple(item[col[0]] for col in self.COLUMNS)
            self.tree.insert("", "end", values=values)
