"""
ui/edit_dialog.py — Rename dialog for fixing improperly-named Switch files.

Shows all bad_name and missing_tid files with auto-proposed corrected names,
lets the user edit proposed names inline, and performs os.rename() on commit.
After a successful batch rename it triggers a re-scan on the parent screen.
"""

import os
import re
import tkinter as tk
from tkinter import ttk, messagebox


# ── helpers ────────────────────────────────────────────────────────────────

_SAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize(name: str) -> str:
    """Strip filesystem-illegal characters and trim whitespace/dots."""
    return _SAFE_RE.sub('', name).strip(' .')


def _propose_name(item: dict, norm_t: dict) -> str | None:
    """
    Return a properly-formatted filename for *item*, or None if impossible.

    Target convention:  Game Name [TITLEID][vVERSION].ext
    """
    fname   = item.get("filename", "")
    tid_raw = item.get("tid", "—")

    if tid_raw == "—":
        return None          # no TID → cannot propose

    tid_upper = tid_raw.upper()
    tid_lower = tid_raw.lower()
    ext       = os.path.splitext(fname)[1].lower()

    # Version integer — use values already parsed by the scan method so we
    # never accidentally match a display string like "v1.4.643" from the stem.
    # • Updates carry "cur_int" (e.g. 262144)
    # • Base games are always v0 by Switch convention
    # • DLC: look for a bracketed [vNUMBER] token (TIDs have no v-prefix)
    if "cur_int" in item:
        ver_int = item["cur_int"]
    elif "version" in item:
        ver_int = 0                     # base games are always v0
    else:
        ver_m   = re.search(r'\[v(\d+)\]', fname, re.IGNORECASE)
        ver_int = int(ver_m.group(1)) if ver_m else 0

    # DB name lookup — try the file's own TID first, then the base-game TID.
    # Update/DLC TIDs often have no "name" entry; the base game TID does.
    base_tid = tid_lower[:13] + "000"
    db_entry = norm_t.get(tid_lower) or norm_t.get(base_tid) or {}
    db_name  = (db_entry.get("name") or "").strip()

    if db_name:
        safe_name = _sanitize(db_name)
    else:
        # Fallback: scrub the stem of TID, version tokens, and noise tags.
        stem = os.path.splitext(fname)[0]
        # Remove TID with or without surrounding brackets
        stem = re.sub(r'(?i)\[?' + re.escape(tid_upper) + r'\]?', ' ', stem)
        # Remove bracketed version tokens: [v12345] or [12345]
        stem = re.sub(r'\[v?\d+\]', ' ', stem, flags=re.IGNORECASE)
        # Remove display version strings: v1.4.643, V2.0, etc. (not preceded by a letter)
        stem = re.sub(r'(?<![A-Za-z])[vV][\d.]+', ' ', stem)
        # Remove noise tags and leftover bracket pairs
        stem = re.sub(r'(?i)\[?(UPD|DLC|Switch)\]?', ' ', stem)
        stem = re.sub(r'[\[\]]', ' ', stem)
        stem = re.sub(r'\s+', ' ', stem).strip()
        safe_name = _sanitize(stem)

    if not safe_name:
        return None

    return f"{safe_name} [{tid_upper}][v{ver_int}]{ext}"


# ── dialog ─────────────────────────────────────────────────────────────────

_T = {
    "bg":         "#0a0a14",
    "bg_card":    "#151d33",
    "bg_hover":   "#1f2847",
    "border":     "#2a3f5f",
    "border_lt":  "#3a4a6f",
    "text":       "#ffffff",
    "text_dim":   "#9ca3af",
    "text_muted": "#6b7280",
    "accent":     "#60a5fa",
    "ok":         "#10b981",
    "warn":       "#f97316",
    "danger":     "#ef4444",
}


class EditDialog(tk.Toplevel):
    """
    Modal rename dialog.

    Parameters
    ----------
    parent_screen : BaseScreen subclass
        The calling screen; ``parent_screen.scan()`` is called after renames.
    items : list[dict]
        Entries from ``all_data`` whose ``_quality`` is 'bad_name' or
        'missing_tid'.
    norm_t : dict
        Title database for name lookups.
    folder : str
        Root folder of the library (informational; actual path comes from
        ``item['filepath']``).
    """

    def __init__(self, parent_screen, items: list, norm_t: dict, folder: str,
                 search: str = ""):
        super().__init__(parent_screen)
        self._parent = parent_screen
        self._norm_t = norm_t
        self._folder = folder
        self._search_var = tk.StringVar(value=search)

        # Build the rename plan before drawing anything
        self._plan = self._build_plan(items)

        self.title("Rename Files")
        self.resizable(True, True)
        self.geometry("1060x640")
        self.configure(bg=_T["bg"])
        self.grab_set()
        self.transient(parent_screen)

        self._build_ui()
        self._update_summary()

        # Wire up live search after UI exists; apply initial filter if pre-filled
        self._search_var.trace_add("write", self._apply_filter)
        if search:
            self._apply_filter()

        # Centre on parent
        self.update_idletasks()
        px = parent_screen.winfo_rootx()
        py = parent_screen.winfo_rooty()
        pw = parent_screen.winfo_width()
        ph = parent_screen.winfo_height()
        x  = px + (pw - self.winfo_width())  // 2
        y  = py + (ph - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    # ── plan construction ──────────────────────────────────────────────────

    def _build_plan(self, items: list) -> list:
        plan = []
        for item in items:
            quality  = item.get("_quality", "ok")
            proposed = _propose_name(item, self._norm_t)
            plan.append({
                "item":     item,
                "quality":  quality,
                "proposed": proposed or "",
                "var":      tk.BooleanVar(value=proposed is not None),
                "can_auto": proposed is not None,
                "prop_var": None,   # filled in _add_row
            })
        return plan

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Title bar ──────────────────────────────────────────────────────
        title_bar = tk.Frame(self, bg=_T["bg_card"],
                             highlightthickness=1, highlightbackground=_T["border"])
        title_bar.pack(fill="x")

        tk.Label(title_bar, text="✎  RENAME FILES",
                 font=("Segoe UI", 13, "bold"),
                 fg=_T["text"], bg=_T["bg_card"],
                 padx=20, pady=14).pack(side="left")

        self._summary_lbl = tk.Label(title_bar, text="",
                                     font=("Segoe UI", 9),
                                     fg=_T["text_dim"], bg=_T["bg_card"], padx=20)
        self._summary_lbl.pack(side="right")

        # ── Search bar ─────────────────────────────────────────────────────
        search_bar = tk.Frame(self, bg=_T["bg_card"],
                              highlightthickness=1, highlightbackground=_T["border"])
        search_bar.pack(fill="x")

        sb_inner = tk.Frame(search_bar, bg=_T["bg_card"])
        sb_inner.pack(fill="x", padx=14, pady=8)

        tk.Label(sb_inner, text="🔍", font=("Segoe UI", 10),
                 fg=_T["text_dim"], bg=_T["bg_card"]).pack(side="left", padx=(0, 6))

        self._search_entry = tk.Entry(sb_inner, textvariable=self._search_var,
                                      font=("Segoe UI", 9),
                                      bg=_T["bg_hover"], fg=_T["text"],
                                      relief="solid", bd=1,
                                      insertbackground=_T["accent"])
        self._search_entry.pack(side="left", fill="x", expand=True)
        self._search_entry.focus_set()

        tk.Button(sb_inner, text="✕ Clear",
                  command=lambda: self._search_var.set(""),
                  bg=_T["border_lt"], fg=_T["text_dim"],
                  relief="flat", font=("Segoe UI", 8),
                  cursor="hand2", padx=8, pady=3).pack(side="left", padx=(8, 0))

        # ── Column headers ─────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=_T["border_lt"],
                       highlightthickness=1, highlightbackground=_T["border"])
        hdr.pack(fill="x", pady=(1, 0))

        hdr_inner = tk.Frame(hdr, bg=_T["border_lt"])
        hdr_inner.pack(fill="x", padx=14, pady=6)

        tk.Label(hdr_inner, text="", width=2,
                 bg=_T["border_lt"]).pack(side="left")
        tk.Label(hdr_inner, text="CURRENT FILENAME",
                 font=("Segoe UI", 8, "bold"), fg=_T["text_dim"],
                 bg=_T["border_lt"], width=44, anchor="w").pack(side="left", padx=(4, 0))
        tk.Label(hdr_inner, text="→",
                 font=("Segoe UI", 9), fg=_T["text_muted"],
                 bg=_T["border_lt"], width=3, anchor="center").pack(side="left")
        tk.Label(hdr_inner, text="PROPOSED FILENAME  (click to edit)",
                 font=("Segoe UI", 8, "bold"), fg=_T["text_dim"],
                 bg=_T["border_lt"], anchor="w").pack(side="left", padx=(4, 0))

        # ── Scrollable row list ─────────────────────────────────────────────
        list_outer = tk.Frame(self, bg=_T["bg"])
        list_outer.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(list_outer, bg=_T["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(list_outer, orient="vertical",
                            command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._rows_frame = tk.Frame(self._canvas, bg=_T["bg"])
        self._win_id = self._canvas.create_window(
            (0, 0), window=self._rows_frame, anchor="nw")

        self._rows_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")))
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._win_id, width=e.width))

        # Mouse-wheel scrolling — bind only while cursor is inside the canvas
        self._canvas.bind(
            "<Enter>",
            lambda e: self._canvas.bind_all("<MouseWheel>", self._on_wheel))
        self._canvas.bind(
            "<Leave>",
            lambda e: self._canvas.unbind_all("<MouseWheel>"))

        # Populate rows
        for idx, entry in enumerate(self._plan):
            self._add_row(entry, idx)

        # ── Footer ──────────────────────────────────────────────────────────
        footer = tk.Frame(self, bg=_T["bg_card"],
                          highlightthickness=1, highlightbackground=_T["border"])
        footer.pack(fill="x", side="bottom")

        fi = tk.Frame(footer, bg=_T["bg_card"])
        fi.pack(fill="x", padx=16, pady=12)

        tk.Button(fi, text="Select All",
                  command=self._select_all,
                  bg=_T["border_lt"], fg=_T["text_dim"],
                  relief="flat", font=("Segoe UI", 9),
                  cursor="hand2", padx=10, pady=4).pack(side="left", padx=(0, 6))

        tk.Button(fi, text="Deselect All",
                  command=self._deselect_all,
                  bg=_T["border_lt"], fg=_T["text_dim"],
                  relief="flat", font=("Segoe UI", 9),
                  cursor="hand2", padx=10, pady=4).pack(side="left", padx=(0, 16))

        tk.Button(fi, text="Close",
                  command=self.destroy,
                  bg=_T["border_lt"], fg=_T["text_dim"],
                  relief="flat", font=("Segoe UI", 9, "bold"),
                  cursor="hand2", padx=14, pady=4).pack(side="right")

        self._rename_btn = tk.Button(fi, text="⟳  Rename Checked Files",
                                     command=self._do_rename,
                                     bg=_T["accent"], fg=_T["bg"],
                                     relief="flat", font=("Segoe UI", 9, "bold"),
                                     cursor="hand2", padx=14, pady=4)
        self._rename_btn.pack(side="right", padx=(0, 8))

    def _add_row(self, entry: dict, idx: int):
        bg = _T["bg_card"] if idx % 2 == 0 else _T["bg"]

        row = tk.Frame(self._rows_frame, bg=bg,
                       highlightthickness=1, highlightbackground=_T["border"])
        row.pack(fill="x", pady=(0, 1))
        entry["row_frame"] = row

        inner = tk.Frame(row, bg=bg)
        inner.pack(fill="x", padx=14, pady=7)

        # Checkbox
        chk = tk.Checkbutton(inner, variable=entry["var"],
                             bg=bg, activebackground=bg,
                             selectcolor="#ffffff",
                             command=self._update_summary)
        chk.pack(side="left")
        if not entry["can_auto"]:
            chk.config(state="disabled")
            entry["var"].set(False)

        # Current filename (fixed width, truncated with tooltip if long)
        fname = entry["item"]["filename"]
        display = fname if len(fname) <= 46 else fname[:43] + "…"
        cur_lbl = tk.Label(inner, text=display, width=46, anchor="w",
                           font=("Segoe UI", 9),
                           fg=_T["text"] if entry["can_auto"] else _T["text_muted"],
                           bg=bg)
        cur_lbl.pack(side="left", padx=(6, 0))
        if fname != display:
            _add_tooltip(cur_lbl, fname)

        # Arrow
        tk.Label(inner, text="→", font=("Segoe UI", 10),
                 fg=_T["text_muted"], bg=bg,
                 width=3, anchor="center").pack(side="left")

        # Proposed field
        if entry["can_auto"]:
            prop_var = tk.StringVar(value=entry["proposed"])
            entry["prop_var"] = prop_var
            prop_entry = tk.Entry(inner, textvariable=prop_var,
                                  font=("Segoe UI", 9),
                                  bg=_T["bg_hover"], fg=_T["text"],
                                  relief="solid", bd=1,
                                  insertbackground=_T["accent"])
            prop_entry.pack(side="left", fill="x", expand=True)
        else:
            qual = entry["quality"]
            reason = ("No title ID — rename manually"
                      if qual == "missing_tid"
                      else "No DB entry for this TID — rename manually")
            tk.Label(inner, text=reason, anchor="w",
                     font=("Segoe UI", 9, "italic"),
                     fg=_T["text_muted"], bg=bg).pack(side="left", padx=(4, 0))

    def _on_wheel(self, event):
        self._canvas.yview_scroll(-1 * (event.delta // 120), "units")

    # ── search / filter ────────────────────────────────────────────────────

    def _visible_entries(self) -> list:
        """Return plan entries that match the current search text."""
        q = self._search_var.get().lower()
        if not q:
            return list(self._plan)
        return [e for e in self._plan
                if q in e["item"]["filename"].lower()
                or q in e["proposed"].lower()]

    def _apply_filter(self, *_):
        visible_set = set(id(e) for e in self._visible_entries())
        for entry in self._plan:
            frame = entry.get("row_frame")
            if frame is None:
                continue
            if id(entry) in visible_set:
                frame.pack(fill="x", pady=(0, 1))
            else:
                frame.pack_forget()
        self._rows_frame.event_generate("<Configure>")
        self._update_summary()

    # ── controls ──────────────────────────────────────────────────────────

    def _select_all(self):
        for entry in self._visible_entries():
            if entry["can_auto"]:
                entry["var"].set(True)
        self._update_summary()

    def _deselect_all(self):
        for entry in self._visible_entries():
            entry["var"].set(False)
        self._update_summary()

    def _update_summary(self):
        visible = self._visible_entries()
        checked = sum(1 for e in visible if e["var"].get())
        auto    = sum(1 for e in visible if e["can_auto"])
        cant    = len(visible) - auto
        total   = len(self._plan)
        parts   = [f"{checked} of {auto} selected for rename"]
        if len(visible) < total:
            parts.append(f"{len(visible)} of {total} shown")
        if cant:
            parts.append(f"{cant} cannot be auto-renamed")
        self._summary_lbl.config(text="  •  ".join(parts))

    # ── rename execution ──────────────────────────────────────────────────

    def _do_rename(self):
        to_rename = [e for e in self._plan if e["var"].get() and e["can_auto"]]
        if not to_rename:
            messagebox.showinfo("Nothing to do",
                                "No files are checked for renaming.", parent=self)
            return

        ok, skip, errors = 0, 0, []

        for entry in to_rename:
            item     = entry["item"]
            filepath = item.get("filepath", "")
            proposed = (entry.get("prop_var") or tk.StringVar()).get().strip()

            if not filepath or not proposed:
                skip += 1
                continue

            new_path = os.path.join(os.path.dirname(filepath), proposed)

            # Skip if target already exists (and isn't the same file)
            if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(filepath):
                errors.append(f"Skipped (target exists): {proposed}")
                skip += 1
                continue

            try:
                os.rename(filepath, new_path)
                ok += 1
            except OSError as exc:
                errors.append(f"{item['filename']}: {exc}")
                skip += 1

        # Report
        msg = f"Renamed: {ok}"
        if skip:
            msg += f"  |  Skipped / errors: {skip}"
        if errors:
            msg += "\n\nDetails:\n" + "\n".join(errors[:15])
            messagebox.showwarning("Rename Complete", msg, parent=self)
        else:
            messagebox.showinfo("Rename Complete", msg, parent=self)

        if ok:
            self.destroy()
            self._parent.scan()


# ── tooltip helper ─────────────────────────────────────────────────────────

def _add_tooltip(widget, text: str):
    """Attach a simple hover tooltip to *widget*."""

    tip = None

    def show(event):
        nonlocal tip
        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 4}")
        tk.Label(tip, text=text,
                 font=("Segoe UI", 8),
                 bg="#1f2847", fg="#ffffff",
                 relief="solid", bd=1, padx=6, pady=3).pack()

    def hide(event):
        nonlocal tip
        if tip:
            tip.destroy()
            tip = None

    widget.bind("<Enter>", show)
    widget.bind("<Leave>", hide)
