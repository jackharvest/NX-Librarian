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
import configparser
from collections import defaultdict
import tkinter as tk
from tkinter import messagebox, ttk

from constants import KNOWN_REGIONS, REGION_FLAGS, HAND_CURSOR, UI_FONT, FONT_BOOST, is_clean_filename, CONFIG_FILE
from db import cache_age_string
from ui.base_screen import BaseScreen, THEME
from ui import icon_cache
from debug_region import log_region_lookup, clear_log, get_region_from_votes

_F = FONT_BOOST


_COLUMNS = [
    ("filename",     "FILENAME",      300, True,  "w"),
    ("filetype",     "TYPE",           60, False, "center"),
    ("tid",          "TITLE ID",      155, False, "center"),
    ("version",      "VERSION",       100, False, "center"),
    ("release_date", "RELEASE DATE",  135, False, "center"),
    ("has_update",   "UPDATE?",       115, False, "center"),
    ("has_dlc",      "DLC?",          115, False, "center"),
    ("rgn",          "RGN",            65, False, "center"),
]


class BaseGamesScreen(BaseScreen):
    MODE_KEY     = "base"
    MODE_LABEL   = "BASE GAME LIBRARY"
    ACCENT_COLOR = "#ff3b5c"
    COLUMNS      = _COLUMNS
    TREE_STYLE   = "BaseGames.Treeview"

    def __init__(self, *args, **kwargs):
        self.show_update_missing = False   # "Update Missing" toggle
        self.dlc_filter_state    = 0       # 0=off  1=Missing  2=Partial
        self._art_labels         = []
        self._art_hover_iid      = None
        self._art_hover_clear_id = None
        super().__init__(*args, **kwargs)
        # Apply taller rows immediately if art mode was already on at startup
        if icon_cache.is_enabled():
            self.tree.config(style="BaseGames.Art.Treeview")
        # Rebind tree <Leave> to also clear art hover state
        self.tree.bind("<Leave>",
            lambda e: (self.tree.config(cursor=""), self._schedule_art_hover_clear()))

    # ------------------------------------------------------------------
    # Styles — custom per-screen so row height can differ from other screens
    # ------------------------------------------------------------------

    def _setup_styles(self):
        super()._setup_styles()
        style = ttk.Style()
        for name, rowh in [("BaseGames.Treeview", 58), ("BaseGames.Art.Treeview", 76)]:
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
    # Filter buttons — modern chip-style
    # ------------------------------------------------------------------

    def _build_filter_buttons(self, parent):
        """Filter chips — styled Labels."""
        from ui.tooltip import ComicTooltip

        def _chip(text, cmd, off_bg="#2a3f5f", off_fg="#9ca3af"):
            lbl = tk.Label(parent, text=text, bg=off_bg, fg=off_fg,
                           font=(UI_FONT, 9 + _F, "bold"), cursor=HAND_CURSOR, padx=10, pady=6)
            lbl.bind("<Button-1>", lambda e: cmd())
            return lbl

        def _div():
            tk.Frame(parent, bg="#2a3f5f", width=1).pack(side="left", fill="y", pady=8, padx=6)

        # Update Missing button (simple toggle)
        self.btn_update_missing = _chip("⬆ Update Missing", self._toggle_update_missing)
        self.btn_update_missing.pack(side="left")
        ComicTooltip(self.btn_update_missing,
                     "Show only games where an update was released but you don't have it.",
                     accent_color="#f97316")

        _div()

        # DLC filter (three-way: off → Missing → Partial → off)
        self.btn_dlc_filter = _chip("DLC Missing", self._cycle_dlc_filter)
        self.btn_dlc_filter.pack(side="left")
        ComicTooltip(self.btn_dlc_filter,
                     "Cycle DLC filter: Off → show games with missing DLC → show games with partial DLC.",
                     accent_color="#a78bfa")

    # DLC filter cycle labels/colors
    _DLC_STATES = [
        # (label,            bg,        fg)
        ("DLC Missing",  "#2a3f5f", "#9ca3af"),   # 0 = off
        ("DLC Missing",  "#f97316", "#0a0a14"),   # 1 = Missing active
        ("DLC Partial",  "#a78bfa", "#0a0a14"),   # 2 = Partial active
    ]

    def _toggle_update_missing(self):
        self.show_update_missing = not self.show_update_missing
        self.btn_update_missing.config(
            bg="#f97316" if self.show_update_missing else "#2a3f5f",
            fg="#0a0a14" if self.show_update_missing else "#9ca3af")
        self.refresh_table()

    def _cycle_dlc_filter(self):
        self.dlc_filter_state = (self.dlc_filter_state + 1) % 3
        label, bg, fg = self._DLC_STATES[self.dlc_filter_state]
        self.btn_dlc_filter.config(text=label, bg=bg, fg=fg)
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

        self.all_data  = []
        missing_tid    = 0
        improper_name  = 0
        unknown_tid    = 0

        # ── Pre-scan updates & DLC folders to detect local possession ──────
        cfg = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            cfg.read(CONFIG_FILE)
        updates_folder = cfg.get("Folders", "folder_updates", fallback="")
        dlc_folder     = cfg.get("Folders", "folder_dlc",     fallback="")

        _tid_re = re.compile(r'(?<![0-9A-Fa-f])([01][0-9A-Fa-f]{15})(?![0-9A-Fa-f])')

        local_update_base_tids: set = set()
        upd_folder_ok = bool(updates_folder and os.path.isdir(updates_folder))
        if upd_folder_ok:
            for ufname in os.listdir(updates_folder):
                if not ufname.lower().endswith(('.nsp', '.xci')):
                    continue
                m = _tid_re.search(ufname)
                if m:
                    ut = m.group(1).lower()
                    if ut.endswith('800'):
                        local_update_base_tids.add(ut[:13] + "000")

        # Pre-compute DB DLC counts from norm_c (same logic as DLC screen)
        db_dlc_counts: dict = defaultdict(int)      # base_tid → DB count
        for tid_key, cnmt_info in (self.norm_c or {}).items():
            if isinstance(cnmt_info, dict) and cnmt_info.get("type") == "AddOnContent":
                parent = cnmt_info.get("parent", "")
                if parent:
                    db_dlc_counts[parent] += 1

        local_dlc_counts: dict = defaultdict(int)   # base_tid → local count
        dlc_folder_ok = bool(dlc_folder and os.path.isdir(dlc_folder))
        if dlc_folder_ok:
            for dfname in os.listdir(dlc_folder):
                if not dfname.lower().endswith(('.nsp', '.xci')):
                    continue
                m = _tid_re.search(dfname)
                if m:
                    dt = m.group(1).lower()
                    if dt[-3:] not in ('000', '800'):
                        cnmt  = (self.norm_c or {}).get(dt, {})
                        par   = cnmt.get("parent") if cnmt else None
                        local_dlc_counts[par or (dt[:13] + "000")] += 1
        # ───────────────────────────────────────────────────────────────────

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
                    "filename": fname, "filepath": fpath,
                    "filetype": os.path.splitext(fname)[1].lstrip(".").upper(),
                    "tid": "—", "version": "—",
                    "release_date": "—", "has_update": "—", "has_dlc": "—",
                    "has_update_db": False, "has_dlc_db": False,
                    "rgn": "—", "_quality": "missing_tid",
                })
                continue

            # Strictly named = TID in brackets AND version in brackets
            is_bad_name = not is_clean_filename(fname)
            if is_bad_name:
                improper_name += 1

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

            # Does an update exist in DB?
            update_tid = base_tid[:-3] + "800"
            v_list = norm_v.get(update_tid) or norm_v.get(base_tid)
            has_update_flag = False
            if v_list:
                ints = [int(v) for v in (v_list.keys() if isinstance(v_list, dict) else v_list)
                       if str(v).isdigit()]
                has_update_flag = bool(ints)

            # DLC counts (DB vs local)
            db_dlc_n     = db_dlc_counts[base_tid]
            local_dlc_n  = local_dlc_counts[base_tid]
            has_dlc_flag = db_dlc_n > 0

            # Local possession
            has_update_local = base_tid in local_update_base_tids

            # Two-line column strings
            if has_update_flag:
                if upd_folder_ok:
                    line2_upd = "✓ Acquired" if has_update_local else "— Missing"
                else:
                    line2_upd = "? Set folder"
                update_str = f"✓ Released\n{line2_upd}"
            else:
                update_str = "—"

            if has_dlc_flag:
                if dlc_folder_ok:
                    if local_dlc_n >= db_dlc_n:
                        line2_dlc = "✓ Acquired"
                    elif local_dlc_n > 0:
                        line2_dlc = "⚠ Partial"
                    else:
                        line2_dlc = "— Missing"
                else:
                    line2_dlc = "? Set folder"
                dlc_str = f"✓ Released\n{line2_dlc}"
            else:
                dlc_str = "—"

            self.all_data.append({
                "filename":      fname,
                "filepath":      fpath,
                "filetype":      os.path.splitext(fname)[1].lstrip(".").upper(),
                "tid":           tid.upper(),
                "version":       version,
                "release_date":  release_date,
                "has_update":    update_str,
                "has_dlc":       dlc_str,
                "has_update_db": has_update_flag,
                "has_dlc_db":    has_dlc_flag,
                "rgn":           REGION_FLAGS.get(region, region),
                "_quality":      "bad_name" if is_bad_name else (
                                 "unknown_tid" if not db_entry else "ok"),
            })
            if not is_bad_name and not db_entry:
                unknown_tid += 1

        self.all_data.sort(key=lambda x: x["filename"].lower())
        self._update_file_counters(missing_tid, improper_name, unknown_tid)
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
            upd_val = row.get("has_update", "")
            dlc_val = row.get("has_dlc",    "")
            if self.show_update_missing and "Missing" not in upd_val:
                continue
            if self.dlc_filter_state == 1 and "Missing" not in dlc_val:
                continue
            if self.dlc_filter_state == 2 and "Partial" not in dlc_val:
                continue

            # Build values — format version display
            values = []
            for col_id, _, _, _, _ in self.COLUMNS:
                val = row[col_id]
                if col_id == "version":
                    ver = val if isinstance(val, int) else 0
                    val = "v0" if ver == 0 else f"v{ver}"
                values.append(val)
            values = tuple(values)

            initial_tags = ("unknown_tid",) if row.get("_quality") == "unknown_tid" else ()
            self.tree.insert("", "end", values=values, tags=initial_tags)
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
        
        # Apply row striping — preserve existing quality tags
        for idx, item in enumerate(self.tree.get_children()):
            stripe_tag = "even" if idx % 2 == 0 else "odd"
            existing = self.tree.item(item, "tags")
            self.tree.item(item, tags=(stripe_tag,) + tuple(existing))

        self._schedule_fix_buttons()

    # ------------------------------------------------------------------
    # Version-warn overlays
    # ------------------------------------------------------------------

    def _place_fix_buttons(self):
        """Extend base class to also place version-warn and art overlays."""
        super()._place_fix_buttons()
        self._place_version_warn_overlays()
        self._place_art_overlays()
        # Fix buttons are in table_container; lift them above art labels
        for btn in self._fix_buttons:
            try:
                btn.lift()
            except Exception:
                pass

    def _place_version_warn_overlays(self):
        """Overlay a yellow ⚠ label on the version cell for every v>0 row."""
        from constants import UI_FONT, FONT_BOOST
        fname_idx = next((i for i, c in enumerate(self.COLUMNS) if c[0] == "filename"), 0)
        all_iids  = self.tree.get_children()

        for idx, iid in enumerate(all_iids):
            values = self.tree.item(iid, "values")
            if not values:
                continue
            filename = values[fname_idx]
            item = next((d for d in self.all_data if d.get("filename") == filename), None)
            if not item:
                continue

            ver = item.get("version", 0)
            if not isinstance(ver, int) or ver <= 0:
                continue

            cell = self.tree.bbox(iid, "version")
            if not cell:
                continue

            cx, cy, cw, ch = cell
            row_bg = "#1a2540" if idx % 2 == 0 else "#151d33"

            lbl = tk.Label(
                self.tree,
                text=f"⚠  v{ver}",
                bg=row_bg, fg="#fbbf24",
                font=(UI_FONT, 9 + FONT_BOOST, "bold"),
                cursor=HAND_CURSOR)
            lbl.bind("<Button-1>", lambda e, i=item: self._open_version_warn(i))
            lbl.place(x=cx, y=cy, width=cw, height=ch)
            self._fix_buttons.append(lbl)

    def _open_version_warn(self, item: dict):
        from ui.version_warn_dialog import VersionWarnDialog
        VersionWarnDialog(self, item, self.norm_t)

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
        """Reposition art labels on every smooth-scroll animation frame."""
        self._place_art_overlays()
        for btn in self._fix_buttons:
            try:
                btn.lift()
            except Exception:
                pass

    def _forward_scroll(self, event):
        """Forward mouse-wheel events from art labels to the smooth scroller."""
        if event.num == 4:
            self._push_scroll(-1.0)
        elif event.num == 5:
            self._push_scroll(1.0)
        else:
            self._push_scroll(-event.delta / 120.0)

    def _place_art_overlays(self):
        """Maintain art overlay labels for every visible row.

        On scroll, existing labels are repositioned in-place rather than
        destroyed and recreated.  This eliminates the black-flash blink from
        the old destroy→recreate cycle.  Only labels for rows that newly
        scroll into view are created; labels for rows that scroll off-screen
        are destroyed.
        """
        if not icon_cache.is_enabled():
            return

        fname_idx  = next((i for i, c in enumerate(self.COLUMNS) if c[0] == "filename"), 0)
        tree_off_x = self.tree.winfo_x()
        tree_off_y = self.tree.winfo_y()

        # ── build desired state for every currently-visible row ──────────
        wanted = {}
        for iid in self.tree.get_children():
            values = self.tree.item(iid, "values")
            if not values:
                continue
            filename = values[fname_idx]
            item = next((d for d in self.all_data if d.get("filename") == filename), None)
            if not item:
                continue
            tid = item.get("tid", "").lower()
            if not tid or tid == "—":
                continue
            db_entry   = self.norm_t.get(tid) or self.norm_t.get(tid[:13] + "000") or {}
            icon_url   = db_entry.get("iconUrl",   "")
            banner_url = db_entry.get("bannerUrl", "")
            if not icon_url and not banner_url:
                continue
            cell = self.tree.bbox(iid, "filename")
            if not cell:
                continue   # scrolled off screen
            cx, cy, cw, ch = cell
            tags = self.tree.item(iid, "tags")
            if "unknown_tid" in tags:
                row_bg = "#2d1f47"
            elif "even" in tags:
                row_bg = "#1a2540"
            else:
                row_bg = "#151d33"
            wanted[iid] = dict(
                tid=tid, filename=filename,
                icon_url=icon_url, banner_url=banner_url,
                row_bg=row_bg,
                abs_x=tree_off_x + cx, abs_y=tree_off_y + cy, cw=cw, ch=ch,
            )

        # ── smart update: reuse / move / create / destroy ────────────────
        existing      = {e["iid"]: e for e in self._art_labels}
        new_art_labels = []

        for iid, info in wanted.items():
            if iid in existing:
                entry = existing.pop(iid)
                # Row still visible — reposition only, no destroy/recreate
                entry["label"].place(x=info["abs_x"], y=info["abs_y"],
                                     width=info["cw"], height=info["ch"])
                # Re-render photo only if cell dimensions or bg changed
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
                # Newly visible row — create a fresh label
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

        # Destroy labels for rows that are no longer visible
        for iid, entry in existing.items():
            if iid == self._art_hover_iid:
                self._art_hover_iid = None
            try:
                entry["label"].destroy()
            except Exception:
                pass

        # Lift all art labels above the Treeview in table_container z-order
        for entry in new_art_labels:
            entry["label"].lift()

        self._art_labels = new_art_labels

    def _art_hover_entry(self, entry: dict, hover: bool):
        """Apply dim/bright state to a single art label entry."""
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
        """Brighten art for new_iid row; dim the previously hovered row."""
        if self._art_hover_clear_id:
            try:
                self.after_cancel(self._art_hover_clear_id)
            except Exception:
                pass
            self._art_hover_clear_id = None
        if new_iid == self._art_hover_iid:
            return
        # Dim old row
        if self._art_hover_iid:
            for en in self._art_labels:
                if en["iid"] == self._art_hover_iid:
                    self._art_hover_entry(en, False)
        # Brighten new row
        self._art_hover_iid = new_iid
        for en in self._art_labels:
            if en["iid"] == new_iid:
                self._art_hover_entry(en, True)

    def _schedule_art_hover_clear(self):
        """Debounce art hover-off to prevent flicker on mouse transitions."""
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
        """Called when an icon download completes (may be on a background thread)."""
        import logging
        logging.getLogger("icon_cache").info("_on_icon_ready(%s): scheduling UI update, art_labels=%d", tid, len(self._art_labels))
        try:
            self.after(0, lambda t=tid: self._update_art_for_tid(t))
        except Exception as exc:
            import logging
            logging.getLogger("icon_cache").error("_on_icon_ready(%s): after() failed — %s", tid, exc)

    def _update_art_for_tid(self, tid: str):
        """Refresh the art label for *tid* once its PIL image is available."""
        import logging
        log = logging.getLogger("icon_cache")
        matches = [e for e in self._art_labels if e["tid"] == tid]
        log.info("_update_art_for_tid(%s): %d matching entries in art_labels", tid, len(matches))
        for entry in matches:
            photo = icon_cache.get_photo(
                entry["tid"], entry["cell_w"], entry["cell_h"],
                entry["row_bg"], hover=False,
                overlay_text=entry.get("overlay_text", ""))
            log.info("_update_art_for_tid(%s): get_photo returned %s", tid, "photo" if photo else "None")
            if photo:
                try:
                    entry["label"].config(image=photo)
                    entry["photo"] = photo
                    self._update_status("🖼 Art loaded", "success")
                except Exception as exc:
                    log.error("_update_art_for_tid(%s): label.config failed — %s", tid, exc)
        if not matches:
            # Labels may have been cleared (scroll/resize) — re-place now
            log.info("_update_art_for_tid(%s): no labels found, triggering re-place", tid)
            self._schedule_fix_buttons()

    def _force_art_download(self, tid: str, icon_url: str, banner_url: str = ""):
        """Clear cache for *tid* and trigger a fresh download."""
        icon_cache.clear_icon(tid)
        icon_cache.request_icon(tid, icon_url, self._on_icon_ready, banner_url=banner_url)
        self._update_status("🖼 Downloading art…", "info")

    def _on_art_mode_changed(self):
        """Called by the app when the user toggles Art Mode in the menu."""
        if icon_cache.is_enabled():
            self.tree.config(style="BaseGames.Art.Treeview")
        else:
            self._clear_art_overlays()
            self.tree.config(style="BaseGames.Treeview")
        icon_cache.invalidate_photo_cache()   # force re-render with current settings
        self.refresh_table()

    def _invalidate_art_renders(self):
        """Drop cached PhotoImages so next placement re-renders with current settings."""
        icon_cache.invalidate_photo_cache()

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
        # Nav-column cursor
        if iid and col_key in ("has_update", "has_dlc"):
            val = self.tree.set(iid, col_key)
            self.tree.config(cursor=HAND_CURSOR if val and val != "—" else "")
        else:
            self.tree.config(cursor="")
        # Art hover — track whichever row the mouse is over
        if iid:
            self._set_art_hover(iid)
        else:
            self._schedule_art_hover_clear()

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
        # Art download — always offered if the DB has an icon URL for this game
        db_entry   = self.norm_t.get(tid) or self.norm_t.get(tid[:13] + "000") or {}
        icon_url   = db_entry.get("iconUrl",   "")
        banner_url = db_entry.get("bannerUrl", "")
        if icon_url or banner_url:
            cached    = tid in icon_cache._pil_cache
            art_label = "🖼  Re-download Art" if cached else "🖼  Download Art"
            add_fn(art_label,
                   lambda t=tid, u=icon_url, b=banner_url: self._force_art_download(t, u, b))
