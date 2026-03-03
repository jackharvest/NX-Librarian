"""
ui/base_games_screen.py — Premium v3 base games mode.

Updated to work with the new sophisticated base_screen design system.
"""

import os
import re
import tkinter as tk
from tkinter import messagebox

from constants import KNOWN_REGIONS, REGION_FLAGS
from db import cache_age_string
from ui.base_screen import BaseScreen


_COLUMNS = [
    ("filename",     "FILENAME",      480, True,  "w"),
    ("tid",          "TITLE ID",      145, False, "center"),
    ("version",      "VERSION",        80, False, "center"),
    ("release_date", "RELEASED",      105, False, "center"),
    ("has_update",   "UPDATE?",        90, False, "center"),
    ("has_dlc",      "DLC?",           70, False, "center"),
    ("status",       "STATUS",        120, False, "center"),
    ("rgn",          "RGN",            70, False, "center"),
]


class BaseGamesScreen(BaseScreen):
    MODE_KEY     = "base"
    MODE_LABEL   = "BASE GAMES LIBRARY"
    ACCENT_COLOR = "#e74c55"
    COLUMNS      = _COLUMNS

    def __init__(self, *args, **kwargs):
        self.hide_has_update = False
        self.hide_no_update  = False
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # Filter buttons
    # ------------------------------------------------------------------

    def _build_filter_buttons(self, parent):
        self.btn_has_update = tk.Button(
            parent, text="Hide Updated",
            command=self._toggle_has_update,
            bg="#2a2a3e", relief="flat", width=14, cursor="hand2",
            fg="#b0b0c8", activebackground="#00a7d8", activeforeground="#0f0f1e",
            font=("Segoe UI", 8, "bold"))
        self.btn_has_update.pack(side="left", padx=(16, 0))

        self.btn_no_update = tk.Button(
            parent, text="Hide No Update",
            command=self._toggle_no_update,
            bg="#2a2a3e", relief="flat", width=16, cursor="hand2",
            fg="#b0b0c8", activebackground="#1dd1a1", activeforeground="#0f0f1e",
            font=("Segoe UI", 8, "bold"))
        self.btn_no_update.pack(side="left", padx=(8, 0))

    def _toggle_has_update(self):
        self.hide_has_update = not self.hide_has_update
        self.btn_has_update.config(
            bg="#00a7d8" if self.hide_has_update else "#2a2a3e",
            fg="#0f0f1e" if self.hide_has_update else "#b0b0c8")
        self.refresh_table()

    def _toggle_no_update(self):
        self.hide_no_update = not self.hide_no_update
        self.btn_no_update.config(
            bg="#e74c55" if self.hide_no_update else "#2a2a3e",
            fg="#0f0f1e" if self.hide_no_update else "#b0b0c8")
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

        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            if not os.path.isfile(fpath):
                continue
            if not fname.lower().endswith(('.nsp', '.xci')):
                continue

            # Title ID from filename
            match = re.search(r'([0-9a-fA-F]{16})', fname)
            if not match:
                continue

            tid = match.group(1).upper()
            base_tid = tid[:-4] + "0000"

            # Version
            version = 0
            try:
                v_match = re.search(r'\[v(\d+)\]', fname, re.IGNORECASE)
                if v_match:
                    version = int(v_match.group(1))
                elif tid != base_tid:
                    version = int(tid[-4:], 16) if tid[-4:].isdigit() else 0
            except Exception:
                pass

            # Region
            region = "—"
            for token in re.findall(r'\[([^\]]+)\]', fname):
                if token.upper() in KNOWN_REGIONS:
                    region = token.upper()
                    break

            # Release date
            db_entry = norm_t.get(tid) or norm_t.get(base_tid) or {}
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

            update_str = "✓ Yes" if has_update_flag else "—"

            # DLC?
            has_dlc_flag = False
            for dlc_tid in norm_t.keys():
                if dlc_tid.startswith(base_tid[:13]):
                    has_dlc_flag = True
                    break
            dlc_str = "✓ Yes" if has_dlc_flag else "—"

            # Status
            status = "OK"
            if not has_update_flag:
                status = "⚠ No Update"

            self.all_data.append({
                "filename":    fname,
                "tid":         tid,
                "version":     version,
                "release_date": release_date,
                "has_update":  update_str,
                "has_dlc":     dlc_str,
                "status":      status,
                "rgn":         REGION_FLAGS.get(region, region),
            })

        self.status_lbl.config(text=f"Found {len(self.all_data)} base games")
        self.refresh_table()

    # ------------------------------------------------------------------
    # Table refresh
    # ------------------------------------------------------------------

    def refresh_table(self):
        """Filter and display table."""
        self.tree.delete(*self.tree.get_children())

        for row in self.all_data:
            # Filter by search
            search_term = self.search_query.get().lower()
            if search_term and search_term not in row["filename"].lower():
                continue

            # Filter by toggle
            if self.hide_has_update and "Yes" in row["has_update"]:
                continue
            if self.hide_no_update and "No Update" in row["status"]:
                continue

            # Insert row
            values = tuple(row[col[0]] for col in self.COLUMNS)
            self.tree.insert("", "end", values=values)
