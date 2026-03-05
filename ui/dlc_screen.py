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
from tkinter import messagebox, ttk
from collections import defaultdict

from constants import KNOWN_REGIONS, REGION_FLAGS, classify_title_id, HAND_CURSOR, UI_FONT, FONT_BOOST, is_clean_filename
from db import cache_age_string
from ui.base_screen import BaseScreen, THEME
from ui import icon_cache
from debug_region import get_region_from_votes

_F = FONT_BOOST


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
    TREE_STYLE   = "DLC.Treeview"

    def __init__(self, *args, **kwargs):
        self.hide_wrong_region   = False
        self.hide_partial        = False
        self._art_labels         = []
        self._art_hover_iid      = None
        self._art_hover_clear_id = None
        super().__init__(*args, **kwargs)
        if icon_cache.is_enabled():
            self.tree.config(style="DLC.Art.Treeview")
        self.tree.bind("<Leave>",
            lambda e: (self.tree.config(cursor=""), self._schedule_art_hover_clear()))

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------

    def _setup_styles(self):
        super()._setup_styles()
        style = ttk.Style()
        for name, rowh in [("DLC.Treeview", 52), ("DLC.Art.Treeview", 72)]:
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
    # Filter buttons
    # ------------------------------------------------------------------

    def _build_filter_buttons(self, parent):
        """Filter chips — styled Labels."""
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
        self.btn_wrong_region = _chip("✗ Wrong Region", self._toggle_wrong_region)
        self.btn_partial      = _chip("⚠ Partial",      self._toggle_partial)
        self.btn_wrong_region.pack(side="left")
        ComicTooltip(self.btn_wrong_region,
                     "Show only DLC files that appear to be from a different region "
                     "than the base game. These may not work correctly.",
                     accent_color="#ef4444")
        _div()
        self.btn_partial.pack(side="left")
        ComicTooltip(self.btn_partial,
                     "Show only games where you have some but not all available DLC. "
                     "Useful for identifying incomplete add-on sets.",
                     accent_color="#f97316")

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
        self._save_folder_config(folder)

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
        unknown_tid   = 0

        id_pat       = re.compile(r'(?<![0-9A-Fa-f])([01][0-9A-Fa-f]{15})(?![0-9A-Fa-f])')
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

                is_bad_name = not is_clean_filename(fname)
                if is_bad_name:
                    improper_name += 1

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
                    "_quality":         "bad_name" if is_bad_name else (
                                        "unknown_tid" if not (parent_entry or dlc_entry) else "ok"),
                })
                if not is_bad_name and not (parent_entry or dlc_entry):
                    unknown_tid += 1

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
            # Skip entirely if parent is GLB: "GLB" is our synthetic label and is never
            # a real key in dlc_votes, so the check would always fire for global games.
            # Also skip if the DLC itself appears in 3+ regional DBs (it's also global).
            dlc_is_glb = len(dlc_votes) >= 3
            if p_region and p_region != "GLB" and dlc_votes and not dlc_is_glb and p_region not in dlc_votes:
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
        self._update_file_counters(missing_tid, improper_name, unknown_tid)
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
            if self.hide_wrong_region and "WRONG REGION" not in status:
                continue
            if self.hide_partial and "PARTIAL" not in status:
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
    # Art Mode overlays
    # ------------------------------------------------------------------

    def _place_fix_buttons(self):
        super()._place_fix_buttons()
        self._place_art_overlays()

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

    def _forward_scroll(self, event):
        if event.num == 4:
            self._push_scroll(-1.0)
        elif event.num == 5:
            self._push_scroll(1.0)
        else:
            self._push_scroll(-event.delta / 120.0)

    def _place_art_overlays(self):
        """Overlay parent-game art on the parent_name column of each visible row."""
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
            # Art is keyed to the parent game TID
            art_tid = item.get("parent_tid", "").lower()
            if not art_tid:
                continue
            db_entry   = self.norm_t.get(art_tid) or {}
            icon_url   = db_entry.get("iconUrl",   "")
            banner_url = db_entry.get("bannerUrl", "")
            if not icon_url and not banner_url:
                continue
            cell = self.tree.bbox(iid, "parent_name")
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
            overlay = item.get("parent_name", "")
            wanted[iid] = dict(
                tid=art_tid, filename=filename,
                icon_url=icon_url, banner_url=banner_url,
                row_bg=row_bg, overlay=overlay,
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
                        hover=False, overlay_text=info["overlay"])
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
                    hover=False, overlay_text=info["overlay"])
                lbl = tk.Label(self.table_container, bd=0,
                               highlightthickness=0, bg=info["row_bg"])
                if photo:
                    lbl.config(image=photo)
                entry = dict(
                    label=lbl, iid=iid, tid=info["tid"],
                    cell_w=info["cw"], cell_h=info["ch"],
                    row_bg=info["row_bg"], photo=photo,
                    overlay_text=info["overlay"],
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
            self.tree.config(style="DLC.Art.Treeview")
        else:
            self._clear_art_overlays()
            self.tree.config(style="DLC.Treeview")
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
                       lambda t=item["parent_tid"]: self.navigate_to("base", t))
                # Art download
                art_tid    = item.get("parent_tid", "").lower()
                db_entry   = self.norm_t.get(art_tid) or {}
                icon_url   = db_entry.get("iconUrl",   "")
                banner_url = db_entry.get("bannerUrl", "")
                if icon_url or banner_url:
                    cached    = art_tid in icon_cache._pil_cache
                    art_label = "🖼  Re-download Art" if cached else "🖼  Download Art"
                    add_fn(art_label,
                           lambda t=art_tid, u=icon_url, b=banner_url: self._force_art_download(t, u, b))
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

