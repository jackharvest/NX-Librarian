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
from tkinter import messagebox, ttk
from collections import defaultdict
import time

from constants import KNOWN_REGIONS, REGION_FLAGS, HAND_CURSOR, UI_FONT, FONT_BOOST, is_clean_filename
from db import cache_age_string
from ui.base_screen import BaseScreen, THEME
from ui import icon_cache
from debug_region import log_region_lookup, clear_log, get_region_from_votes

_F = FONT_BOOST


_COLUMNS = [
    ("filename", "FILENAME",  300, True,  "w"),
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
    TREE_STYLE   = "Updates.Treeview"

    def __init__(self, *args, **kwargs):
        self.hide_latest         = False
        self.hide_outdated       = False
        self.hide_base           = False
        self._art_labels         = []
        self._art_hover_iid      = None
        self._art_hover_clear_id = None
        super().__init__(*args, **kwargs)
        if icon_cache.is_enabled():
            self.tree.config(style="Updates.Art.Treeview")
        self.tree.bind("<Leave>",
            lambda e: (self.tree.config(cursor=""), self._schedule_art_hover_clear()))

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------

    def _setup_styles(self):
        super()._setup_styles()
        style = ttk.Style()
        for name, rowh in [("Updates.Treeview", 52), ("Updates.Art.Treeview", 72)]:
            style.configure(name,
                            font=(UI_FONT, 10 + _F),
                            rowheight=rowh,
                            borderwidth=0,
                            background=THEME["bg_secondary"],
                            foreground=THEME["text_primary"],
                            fieldbackground=THEME["bg_secondary"],
                            relief="flat")
            style.map(name,
                      background=[("selected", THEME["bg_tertiary"])],
                      foreground=[("selected", THEME["accent_primary"])])

    # ------------------------------------------------------------------
    # Filter buttons — modern chip-style filters
    # ------------------------------------------------------------------

    def _build_filter_buttons(self, parent):
        """Filter chips — styled Labels, no Windows 95 buttons."""
        from constants import UI_FONT, FONT_BOOST
        _F = FONT_BOOST

        def _chip(text, cmd, off_bg="#2a3f5f", off_fg="#9ca3af"):
            lbl = tk.Label(parent, text=text, bg=off_bg, fg=off_fg,
                           font=(UI_FONT, 9 + _F, "bold"), cursor=HAND_CURSOR, padx=10, pady=6)
            lbl.bind("<Button-1>", lambda e: cmd())
            return lbl

        def _div():
            tk.Frame(parent, bg="#2a3f5f", width=1).pack(side="left", fill="y", pady=8, padx=6)

        from ui.tooltip import ComicTooltip
        self.btn_latest  = _chip("✓ Latest",     self._toggle_latest)
        self.btn_outdated = _chip("⚠ Old Update", self._toggle_outdated)
        self.btn_base    = _chip("🎮 Base",       self._toggle_base)
        self.btn_latest.pack(side="left")
        ComicTooltip(self.btn_latest,
                     "Show only files that are already the latest known version. "
                     "Click again to return to full view.",
                     accent_color="#60a5fa")
        _div()
        self.btn_outdated.pack(side="left")
        ComicTooltip(self.btn_outdated,
                     "Show only update files where a newer version exists in the database. "
                     "These are superseded patches you may want to replace.",
                     accent_color="#ef4444")
        _div()
        self.btn_base.pack(side="left")
        ComicTooltip(self.btn_base,
                     "Show only files detected as base games sitting in your Updates folder. "
                     "These are likely misplaced and should be moved.",
                     accent_color="#06d6d0")

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
        self._save_folder_config(folder)

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
        unknown_tid   = 0

        id_pat       = re.compile(r'(?<![0-9A-Fa-f])([01][0-9A-Fa-f]{15})(?![0-9A-Fa-f])')
        # Priority order:
        #   1. [v12345]          — canonical bracket+v format
        #   2. [262144]          — bare number in brackets (5-15 digits = 65536..999999999999999)
        #                          min 5 digits excludes years/small tokens; max 15 avoids 16-digit TIDs
        #   3. bare v12345       — no brackets, v prefix, not followed by .\d (display version)
        ver_pat      = re.compile(r'\[v(\d+)\]|\[(\d{5,15})\]|[vV](\d+)(?!\.\d)')
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

                is_bad_name = not is_clean_filename(fname)
                if is_bad_name:
                    improper_name += 1

                tid = tid_m.group(1).lower()
                ver_m = ver_pat.search(fname)
                cur_i = int(ver_m.group(1) or ver_m.group(2) or ver_m.group(3)) if ver_m else 0

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
                # Skip if base is GLB ("GLB" is our synthetic label, never a real votes key)
                # or if the update itself appears in 3+ regions (also global).
                update_is_glb = len(update_votes) >= 3
                wrong_region = bool(
                    base_region and base_region != "GLB"
                    and update_votes and not update_is_glb
                    and base_region not in update_votes
                )

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
                        "_quality": "bad_name" if is_bad_name else (
                                    "unknown_tid" if not db_entry else "ok"),
                    })
                    if not is_bad_name and not db_entry:
                        unknown_tid += 1
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
                    "_quality": "bad_name" if is_bad_name else (
                                "unknown_tid" if not db_entry else "ok"),
                })
                if not is_bad_name and not db_entry:
                    unknown_tid += 1

        self.all_data.sort(key=lambda x: x["filename"].lower())
        self._update_file_counters(missing_tid, improper_name, unknown_tid)
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
            if self.hide_latest and tag != "latest":
                continue
            if self.hide_outdated and tag != "outdated":
                continue
            if self.hide_base and tag != "base":
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
    # Base-game-in-updates overlays  (mirror of base screen's version warn)
    # ------------------------------------------------------------------

    def _place_fix_buttons(self):
        """Extend base class to also overlay ⚠ on v0/base rows and art."""
        super()._place_fix_buttons()
        self._place_base_warn_overlays()
        self._place_art_overlays()
        for btn in self._fix_buttons:
            try:
                btn.lift()
            except Exception:
                pass

    def _place_base_warn_overlays(self):
        """Overlay yellow ⚠ v0 on the CURRENT column for rows tagged 'base'."""
        from constants import UI_FONT, FONT_BOOST
        fname_idx = next((i for i, c in enumerate(self.COLUMNS) if c[0] == "filename"), 0)
        all_iids  = self.tree.get_children()

        for idx, iid in enumerate(all_iids):
            values = self.tree.item(iid, "values")
            if not values:
                continue
            tags = self.tree.item(iid, "tags")
            if "base" not in tags:
                continue

            filename = values[fname_idx]
            item = next((d for d in self.all_data if d.get("filename") == filename), None)
            if not item:
                continue

            cell = self.tree.bbox(iid, "cur_ver")
            if not cell:
                continue

            cx, cy, cw, ch = cell
            row_bg = "#1a2540" if idx % 2 == 0 else "#151d33"

            lbl = tk.Label(
                self.tree,
                text="⚠  v0",
                bg=row_bg, fg="#fbbf24",
                font=(UI_FONT, 9 + FONT_BOOST, "bold"),
                cursor=HAND_CURSOR)
            lbl.bind("<Button-1>", lambda e, i=item: self._open_base_warn(i))
            lbl.place(x=cx, y=cy, width=cw, height=ch)
            self._fix_buttons.append(lbl)

    def _open_base_warn(self, item: dict):
        from ui.version_warn_dialog import BaseMisplacedDialog
        BaseMisplacedDialog(self, item, self.norm_t)

    # ------------------------------------------------------------------
    # Art Mode overlays
    # ------------------------------------------------------------------

    def _clear_art_overlays(self):
        for entry in self._art_labels:
            try:
                entry["label"].destroy()
            except Exception:
                pass
        self._art_labels = []
        self._art_hover_iid = None
        if self._art_hover_clear_id:
            try:
                self.after_cancel(self._art_hover_clear_id)
            except Exception:
                pass
            self._art_hover_clear_id = None

    def _on_scroll_tick(self):
        self._place_art_overlays()
        for btn in self._fix_buttons:
            try:
                btn.lift()
            except Exception:
                pass

    def _forward_scroll(self, event):
        if event.num == 4:
            self._push_scroll(-1.0)
        elif event.num == 5:
            self._push_scroll(1.0)
        else:
            self._push_scroll(-event.delta / 120.0)

    def _place_art_overlays(self):
        """Overlay base-game art on the filename column of each visible row."""
        if not icon_cache.is_enabled():
            return

        fname_idx  = next((i for i, c in enumerate(self.COLUMNS) if c[0] == "filename"), 0)
        tree_off_x = self.tree.winfo_x()
        tree_off_y = self.tree.winfo_y()

        wanted = {}
        for iid in self.tree.get_children():
            values = self.tree.item(iid, "values")
            if not values:
                continue
            filename = values[fname_idx]
            item = next((d for d in self.all_data if d.get("filename") == filename), None)
            if not item:
                continue
            # Art is keyed to the base game TID, not the update TID
            art_tid = item.get("base_tid", "").lower()
            if not art_tid:
                continue
            db_entry   = self.norm_t.get(art_tid) or {}
            icon_url   = db_entry.get("iconUrl",   "")
            banner_url = db_entry.get("bannerUrl", "")
            if not icon_url and not banner_url:
                continue
            cell = self.tree.bbox(iid, "filename")
            if not cell:
                continue
            cx, cy, cw, ch = cell
            tags = self.tree.item(iid, "tags")
            if "unknown_tid" in tags:
                row_bg = "#2d1f47"
            elif "even" in tags:
                row_bg = "#1a2540"
            else:
                row_bg = "#151d33"
            wanted[iid] = dict(
                tid=art_tid, filename=filename,
                icon_url=icon_url, banner_url=banner_url,
                row_bg=row_bg,
                abs_x=tree_off_x + cx, abs_y=tree_off_y + cy, cw=cw, ch=ch,
            )

        existing       = {e["iid"]: e for e in self._art_labels}
        new_art_labels = []

        for iid, info in wanted.items():
            if iid in existing:
                entry = existing.pop(iid)
                entry["label"].place(x=info["abs_x"], y=info["abs_y"],
                                     width=info["cw"], height=info["ch"])
                if (entry["cell_w"] != info["cw"]
                        or entry["cell_h"] != info["ch"]
                        or entry["row_bg"] != info["row_bg"]):
                    entry["cell_w"] = info["cw"]
                    entry["cell_h"] = info["ch"]
                    entry["row_bg"] = info["row_bg"]
                    photo = icon_cache.get_photo(
                        info["tid"], info["cw"], info["ch"], info["row_bg"],
                        hover=False, overlay_text=info["filename"])
                    if photo:
                        try:
                            entry["label"].config(image=photo)
                            entry["photo"] = photo
                        except Exception:
                            pass
                new_art_labels.append(entry)
            else:
                photo = icon_cache.get_photo(
                    info["tid"], info["cw"], info["ch"], info["row_bg"],
                    hover=False, overlay_text=info["filename"])
                lbl = tk.Label(self.table_container, bd=0,
                               highlightthickness=0, bg=info["row_bg"])
                if photo:
                    lbl.config(image=photo)
                entry = dict(
                    label=lbl, iid=iid, tid=info["tid"],
                    cell_w=info["cw"], cell_h=info["ch"],
                    row_bg=info["row_bg"], photo=photo,
                    overlay_text=info["filename"],
                )
                lbl.bind("<Enter>",      lambda e, i=iid: self._set_art_hover(i))
                lbl.bind("<Leave>",      lambda e: self._schedule_art_hover_clear())
                lbl.bind("<Button-1>",   lambda e, i=iid: self.tree.selection_set(i))
                lbl.bind("<MouseWheel>", self._forward_scroll)
                lbl.bind("<Button-4>",   self._forward_scroll)
                lbl.bind("<Button-5>",   self._forward_scroll)
                lbl.place(x=info["abs_x"], y=info["abs_y"],
                          width=info["cw"], height=info["ch"])
                new_art_labels.append(entry)
                icon_cache.request_icon(info["tid"], info["icon_url"], self._on_icon_ready,
                                        banner_url=info["banner_url"])

        for iid, entry in existing.items():
            if iid == self._art_hover_iid:
                self._art_hover_iid = None
            try:
                entry["label"].destroy()
            except Exception:
                pass

        for entry in new_art_labels:
            entry["label"].lift()

        self._art_labels = new_art_labels

    def _art_hover_entry(self, entry: dict, hover: bool):
        photo = icon_cache.get_photo(
            entry["tid"], entry["cell_w"], entry["cell_h"], entry["row_bg"], hover,
            overlay_text=entry.get("overlay_text", ""))
        if photo:
            try:
                entry["label"].config(image=photo)
                entry["photo"] = photo
            except Exception:
                pass

    def _set_art_hover(self, new_iid):
        if self._art_hover_clear_id:
            try:
                self.after_cancel(self._art_hover_clear_id)
            except Exception:
                pass
            self._art_hover_clear_id = None
        if new_iid == self._art_hover_iid:
            return
        if self._art_hover_iid:
            for en in self._art_labels:
                if en["iid"] == self._art_hover_iid:
                    self._art_hover_entry(en, False)
        self._art_hover_iid = new_iid
        for en in self._art_labels:
            if en["iid"] == new_iid:
                self._art_hover_entry(en, True)

    def _schedule_art_hover_clear(self):
        if self._art_hover_clear_id:
            try:
                self.after_cancel(self._art_hover_clear_id)
            except Exception:
                pass
        self._art_hover_clear_id = self.after(30, self._do_art_hover_clear)

    def _do_art_hover_clear(self):
        self._art_hover_clear_id = None
        if self._art_hover_iid:
            for en in self._art_labels:
                if en["iid"] == self._art_hover_iid:
                    self._art_hover_entry(en, False)
            self._art_hover_iid = None

    def _on_icon_ready(self, tid: str):
        try:
            self.after(0, lambda t=tid: self._update_art_for_tid(t))
        except Exception:
            pass

    def _update_art_for_tid(self, tid: str):
        matches = [e for e in self._art_labels if e["tid"] == tid]
        for entry in matches:
            photo = icon_cache.get_photo(
                entry["tid"], entry["cell_w"], entry["cell_h"],
                entry["row_bg"], hover=False,
                overlay_text=entry.get("overlay_text", ""))
            if photo:
                try:
                    entry["label"].config(image=photo)
                    entry["photo"] = photo
                    self._update_status("🖼 Art loaded", "success")
                except Exception:
                    pass
        if not matches:
            self._schedule_fix_buttons()

    def _force_art_download(self, tid: str, icon_url: str, banner_url: str = ""):
        icon_cache.clear_icon(tid)
        icon_cache.request_icon(tid, icon_url, self._on_icon_ready, banner_url=banner_url)
        self._update_status("🖼 Downloading art…", "info")

    def _on_art_mode_changed(self):
        if icon_cache.is_enabled():
            self.tree.config(style="Updates.Art.Treeview")
        else:
            self._clear_art_overlays()
            self.tree.config(style="Updates.Treeview")
        icon_cache.invalidate_photo_cache()
        self.refresh_table()

    def _invalidate_art_renders(self):
        icon_cache.invalidate_photo_cache()

    def _on_tree_motion(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self._set_art_hover(iid)
        else:
            self._schedule_art_hover_clear()

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
                # Art download
                art_tid  = item.get("base_tid", "").lower()
                db_entry = self.norm_t.get(art_tid) or {}
                icon_url   = db_entry.get("iconUrl",   "")
                banner_url = db_entry.get("bannerUrl", "")
                if icon_url or banner_url:
                    cached    = art_tid in icon_cache._pil_cache
                    art_label = "🖼  Re-download Art" if cached else "🖼  Download Art"
                    add_fn(art_label,
                           lambda t=art_tid, u=icon_url, b=banner_url: self._force_art_download(t, u, b))
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

