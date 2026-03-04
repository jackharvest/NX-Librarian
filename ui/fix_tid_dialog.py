"""
ui/fix_tid_dialog.py — Dialog for fixing Missing TID and Unknown TID files.

Searches the title database by name extracted from the filename,
with optional region hints, and proposes corrected filenames.
Works for both missing_tid (no TID in file) and unknown_tid (TID not in DB).
"""

import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
from constants import HAND_CURSOR

_SAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

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
    "purple":     "#a78bfa",
}

# ── helpers ────────────────────────────────────────────────────────────────

def _sanitize(name: str) -> str:
    return _SAFE_RE.sub('', name).strip(' .')


# Region tags commonly found in filenames
_RE_REGION_BRACKET = re.compile(
    r'\[(USA|EUR|JPN|KOR|CHN|ASI|GLB|UKV|WORLD|US|EU|JP|UK)\]', re.IGNORECASE)
_RE_TID   = re.compile(r'(?<![0-9A-Fa-f])[01][0-9A-Fa-f]{15}(?![0-9A-Fa-f])')
_RE_BTID  = re.compile(r'\[[01][0-9A-Fa-f]{15}\]')
_RE_VER   = re.compile(r'\[v?\d+\]', re.IGNORECASE)
_RE_DVER  = re.compile(r'(?<![A-Za-z])[vV][\d.]+')
_RE_NOISE = re.compile(
    r'\[(UPD|DLC|Switch|eShop|NSP|XCI|Base|Update|APP|USA|EUR|JPN|KOR|CHN|ASI|GLB|UKV|WORLD|US|EU|JP|UK)\]',
    re.IGNORECASE)
# Domain patterns like switch-xci.com, nsw2u.com, etc.
_RE_DOMAIN = re.compile(r'\b\w+\.(com|net|org|io|co|me|to)\b', re.IGNORECASE)
_REGION_ALIASES = {'US': 'USA', 'EU': 'EUR', 'JP': 'JPN', 'UK': 'UKV'}

# Words that appear in filenames from scene/warez sites but are not game title words
_SCENE_STOP = {
    'switch', 'xci', 'nsp', 'nsz', 'xcz', 'nsw', 'rom', 'eshop',
    'com', 'net', 'org', 'www', 'site',
    'update', 'upd', 'dlc', 'base', 'app', 'retail',
    'pal', 'ntsc', 'usa', 'eur', 'jpn', 'kor', 'chn', 'asi', 'glb', 'ukv',
    'en', 'ja', 'ko', 'zh',
}


def _tokenize(text: str) -> set:
    """Split text into lowercase words, discarding punctuation and stop words."""
    _stop = {'', 'the', 'a', 'an', 'of', 'in', 'and', 'to', 'is', 'for'} | _SCENE_STOP
    words = re.split(r'[\s:™®©\-–—_.,\'\"!?()]+', text.lower())
    return {w for w in words if w and w not in _stop and not w.isdigit()}


def _extract_search_name(fname: str, bad_tid: str | None = None) -> str:
    """Strip metadata tokens from a filename, leaving just the game name."""
    stem = os.path.splitext(fname)[0]
    # Remove specific bad TID if provided
    if bad_tid:
        stem = re.sub(r'(?i)\[?' + re.escape(bad_tid.upper()) + r'\]?', ' ', stem)
    # Remove TID patterns
    stem = _RE_BTID.sub(' ', stem)
    stem = _RE_TID.sub(' ', stem)
    # Remove version tokens
    stem = _RE_VER.sub(' ', stem)
    stem = _RE_DVER.sub(' ', stem)
    # Remove noise/region bracketed tags
    stem = _RE_NOISE.sub(' ', stem)
    # Remove domain-like patterns (switch-xci.com, nsw2u.net, etc.)
    stem = _RE_DOMAIN.sub(' ', stem)
    # Remove leftover brackets and replace underscores/dots with spaces
    stem = re.sub(r'[\[\]()]', ' ', stem)
    stem = stem.replace('_', ' ').replace('.', ' ')
    stem = re.sub(r'\s+', ' ', stem).strip()

    # Filter out scene stop words, leaving only meaningful title words
    words = [w for w in stem.split() if w.lower() not in _SCENE_STOP and not w.isdigit()]
    return ' '.join(words)


def _extract_region_hint(fname: str) -> str | None:
    """Return the first region tag found in the filename, normalised."""
    m = _RE_REGION_BRACKET.search(fname)
    if m:
        r = m.group(1).upper()
        return _REGION_ALIASES.get(r, r)
    return None


def _search_db_dlc(parent_tid: str, norm_t: dict, norm_c: dict,
                   query: str = "", limit: int = 15) -> list:
    """
    Return DLC candidates for a known parent game TID.

    Looks up all AddOnContent entries in norm_c whose parent matches,
    cross-references norm_t for human-readable names, and optionally
    scores by name similarity to *query* (extracted from the filename).
    """
    all_dlc = []
    q_words = _tokenize(query) if query else set()

    for tid, cnmt_info in (norm_c or {}).items():
        if not isinstance(cnmt_info, dict):
            continue
        if cnmt_info.get("parent") != parent_tid:
            continue
        if cnmt_info.get("type") != "AddOnContent":
            continue

        name_entry = norm_t.get(tid, {})
        name = (name_entry.get("name") or "").strip() or f"DLC [{tid.upper()}]"

        score = 0.0
        if q_words:
            n_words = _tokenize(name)
            overlap = len(q_words & n_words)
            if overlap:
                score = overlap / max(len(q_words), 1) * 10

        all_dlc.append((score, name, tid, name_entry))

    # Sort: best name-match first, then by TID for stable ordering
    all_dlc.sort(key=lambda x: (-x[0], x[2]))
    return all_dlc[:limit]


def _size_score(actual: int, expected: int) -> float:
    """
    Return a 0–15 score based on how closely *actual* file size matches
    the DB *expected* size.  Uses a ratio so it's scale-independent.
    A trimmed XCI or compressed NSP may be smaller, so we don't penalise
    files that are smaller than expected as harshly as ones that are larger.
    """
    if not actual or not expected:
        return 0.0
    ratio = actual / expected
    if ratio > 1:
        ratio = 1 / ratio          # flip so ratio is always ≤ 1
    # ratio 1.0 → score 15, ratio 0.5 → score ~7, ratio 0.1 → score ~1
    return ratio * 15


def _fmt_size(n: int) -> str:
    """Human-readable file size (GB / MB / KB)."""
    if n >= 1_000_000_000:
        return f"{n / 1_073_741_824:.1f} GB"
    if n >= 1_000_000:
        return f"{n / 1_048_576:.1f} MB"
    return f"{n // 1024} KB"


def _search_db(query: str, norm_t: dict, region_hint: str | None = None,
               actual_size: int = 0, limit: int = 15) -> list:
    """
    Search norm_t for titles matching *query* using OR logic.

    Ranking factors (highest to lowest weight):
      - Word coverage  : fraction of query words present in the title
      - Exact substring: full query found inside title name
      - Size proximity : actual file size vs DB expected size (up to +15 pts)
      - Length parity  : similar word-count bonus
      - Region hint    : +4 if DB entry has votes for the hinted region

    Returns list of (score, name, tid, entry) sorted by descending score.
    Only base-game TIDs (ending '000') are returned.
    """
    if not query or not norm_t:
        return []

    query_words = _tokenize(query)
    if not query_words:
        return []
    query_lower = query.lower()

    results = []
    seen = set()

    for tid, entry in norm_t.items():
        if not tid.endswith('000'):
            continue
        name = (entry.get('name') or '').strip()
        if not name or name in seen:
            continue
        name_lower = name.lower()
        name_words = _tokenize(name)

        overlap = len(query_words & name_words)
        if overlap == 0:
            continue  # OR: must share at least one meaningful word

        # Coverage: fraction of query words matched (rewards full matches)
        coverage = overlap / len(query_words)
        score = coverage * 20

        # Exact substring bonuses
        if query_lower in name_lower:
            score += 15
        if name_lower in query_lower:
            score += 8

        # File size proximity — strongest signal when sizes are known
        db_size = entry.get('size') or 0
        score += _size_score(actual_size, db_size)

        # Length similarity — penalise wildly different word counts
        score += min(len(query_words), len(name_words)) / max(len(query_words), len(name_words), 1) * 5

        # Region hint bonus
        if region_hint and region_hint in entry.get('_region_votes', {}):
            score += 4

        results.append((score, name, tid, entry))
        seen.add(name)

    results.sort(key=lambda x: (-x[0], x[1]))
    return results[:limit]


# ── dialog ─────────────────────────────────────────────────────────────────

class FixTidDialog(tk.Toplevel):
    """
    Modal dialog for fixing Missing TID or Unknown TID files.

    Parameters
    ----------
    parent_screen : BaseScreen subclass
    items         : list of dicts with _quality in ('missing_tid', 'unknown_tid')
    norm_t        : title database
    folder        : root folder (for context only)
    focus_filename: if set, pre-filter the list to this filename
    """

    def __init__(self, parent_screen, items: list, norm_t: dict, norm_c: dict,
                 folder: str, focus_filename: str = ""):
        super().__init__(parent_screen)
        self._parent = parent_screen
        self._norm_t = norm_t
        self._norm_c = norm_c or {}
        self._folder = folder
        self._search_var = tk.StringVar(value=focus_filename)

        self._plan = self._build_plan(items)

        self.title("Fix Title ID")
        self.resizable(True, True)
        self.geometry("1120x660")
        self.configure(bg=_T["bg"])
        self.transient(parent_screen)

        self._build_ui()
        self._update_summary()

        self._search_var.trace_add("write", self._apply_filter)
        if focus_filename:
            self._apply_filter()

        self.update_idletasks()
        px, py = parent_screen.winfo_rootx(), parent_screen.winfo_rooty()
        pw, ph = parent_screen.winfo_width(), parent_screen.winfo_height()
        self.geometry(f"+{px + (pw - self.winfo_width()) // 2}+{py + (ph - self.winfo_height()) // 2}")
        self.grab_set()

    # ── plan construction ──────────────────────────────────────────────────

    def _build_plan(self, items: list) -> list:
        plan = []
        for item in items:
            fname   = item.get("filename", "")
            quality = item.get("_quality", "")
            # For unknown_tid, strip the bad TID from the search query
            bad_tid = item.get("tid") if quality == "unknown_tid" else None
            if bad_tid == "—":
                bad_tid = None

            search_name = _extract_search_name(fname, bad_tid=bad_tid)
            region_hint = _extract_region_hint(fname)

            # Actual file size on disk — used to rank DB candidates
            filepath    = item.get("filepath", "")
            actual_size = 0
            try:
                if filepath:
                    actual_size = os.path.getsize(filepath)
            except OSError:
                pass

            # Version: prefer cur_int (updates), fall back to version field
            ver_int = item.get("cur_int") or item.get("version") or 0
            if not isinstance(ver_int, int):
                ver_int = 0

            # Detect mode: DLC items have parent_tid; update items have ver_int > 0
            parent_tid = item.get("parent_tid", "")
            is_dlc     = bool(parent_tid)
            is_update  = (not is_dlc) and (ver_int > 0 or "cur_int" in item)

            if is_dlc:
                candidates = _search_db_dlc(parent_tid, self._norm_t, self._norm_c,
                                            query=search_name)
            else:
                candidates = _search_db(search_name, self._norm_t,
                                        region_hint=region_hint,
                                        actual_size=actual_size)

            ext = os.path.splitext(fname)[1].lower()

            entry = {
                "item":        item,
                "quality":     quality,
                "search_name": search_name,
                "region_hint": region_hint,
                "candidates":  candidates,
                "ver_int":     ver_int,
                "is_update":   is_update,
                "is_dlc":      is_dlc,
                "actual_size": actual_size,
                "ext":         ext,
                "sel_idx":     tk.IntVar(value=0),
                "prop_var":    tk.StringVar(value=""),
                "check_var":   tk.BooleanVar(value=bool(candidates)),
                "row_frame":   None,
                "combo":       None,
            }
            self._refresh_proposed(entry)
            plan.append(entry)
        return plan

    def _refresh_proposed(self, entry: dict):
        """Recompute the proposed filename from the current candidate selection."""
        cands = entry["candidates"]
        idx   = entry["sel_idx"].get()
        if not cands or idx >= len(cands):
            entry["prop_var"].set("")
            return
        _, name, matched_tid, _ = cands[idx]
        safe = _sanitize(name)
        if entry["is_update"]:
            # Candidate is a base TID — convert to update TID
            tid = matched_tid[:13] + "800"
        else:
            # DLC: matched_tid is already the actual DLC TID
            # Base: matched_tid is already the base TID
            tid = matched_tid
        entry["prop_var"].set(f"{safe} [{tid.upper()}][v{entry['ver_int']}]{entry['ext']}")

    # ── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Title bar
        title_bar = tk.Frame(self, bg=_T["bg_card"],
                             highlightthickness=1, highlightbackground=_T["border"])
        title_bar.pack(fill="x")
        tk.Label(title_bar, text="🔧  FIX TITLE ID",
                 font=("Segoe UI", 13, "bold"),
                 fg=_T["text"], bg=_T["bg_card"],
                 padx=20, pady=14).pack(side="left")
        self._summary_lbl = tk.Label(title_bar, text="",
                                     font=("Segoe UI", 9),
                                     fg=_T["text_dim"], bg=_T["bg_card"], padx=20)
        self._summary_lbl.pack(side="right")

        # Search bar
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
                  cursor=HAND_CURSOR, padx=8, pady=3).pack(side="left", padx=(8, 0))

        # Column headers
        hdr = tk.Frame(self, bg=_T["border_lt"],
                       highlightthickness=1, highlightbackground=_T["border"])
        hdr.pack(fill="x", pady=(1, 0))
        hdr_inner = tk.Frame(hdr, bg=_T["border_lt"])
        hdr_inner.pack(fill="x", padx=14, pady=6)
        tk.Label(hdr_inner, text="", width=2, bg=_T["border_lt"]).pack(side="left")
        tk.Label(hdr_inner, text="CURRENT FILENAME",
                 font=("Segoe UI", 8, "bold"), fg=_T["text_dim"],
                 bg=_T["border_lt"], width=36, anchor="w").pack(side="left", padx=(4, 0))
        tk.Label(hdr_inner, text="→", font=("Segoe UI", 9),
                 fg=_T["text_muted"], bg=_T["border_lt"],
                 width=2, anchor="center").pack(side="left")
        tk.Label(hdr_inner, text="BEST DB MATCH  (dropdown to change)",
                 font=("Segoe UI", 8, "bold"), fg=_T["text_dim"],
                 bg=_T["border_lt"], width=36, anchor="w").pack(side="left", padx=(4, 0))
        tk.Label(hdr_inner, text="PROPOSED FILENAME  (click to edit)",
                 font=("Segoe UI", 8, "bold"), fg=_T["text_dim"],
                 bg=_T["border_lt"], anchor="w").pack(side="left", padx=(4, 0))

        # Scrollable rows
        list_outer = tk.Frame(self, bg=_T["bg"])
        list_outer.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(list_outer, bg=_T["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(list_outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._rows_frame = tk.Frame(self._canvas, bg=_T["bg"])
        self._win_id = self._canvas.create_window((0, 0), window=self._rows_frame, anchor="nw")
        self._rows_frame.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(self._win_id, width=e.width))
        self._canvas.bind("<Enter>",
            lambda e: self._canvas.bind_all("<MouseWheel>", self._on_wheel))
        self._canvas.bind("<Leave>",
            lambda e: self._canvas.unbind_all("<MouseWheel>"))

        for idx, entry in enumerate(self._plan):
            self._add_row(entry, idx)

        # Footer
        footer = tk.Frame(self, bg=_T["bg_card"],
                          highlightthickness=1, highlightbackground=_T["border"])
        footer.pack(fill="x", side="bottom")
        fi = tk.Frame(footer, bg=_T["bg_card"])
        fi.pack(fill="x", padx=16, pady=12)

        tk.Button(fi, text="Select All", command=self._select_all,
                  bg=_T["border_lt"], fg=_T["text_dim"],
                  relief="flat", font=("Segoe UI", 9),
                  cursor=HAND_CURSOR, padx=10, pady=4).pack(side="left", padx=(0, 6))
        tk.Button(fi, text="Deselect All", command=self._deselect_all,
                  bg=_T["border_lt"], fg=_T["text_dim"],
                  relief="flat", font=("Segoe UI", 9),
                  cursor=HAND_CURSOR, padx=10, pady=4).pack(side="left")

        tk.Button(fi, text="Close", command=self.destroy,
                  bg=_T["border_lt"], fg=_T["text_dim"],
                  relief="flat", font=("Segoe UI", 9, "bold"),
                  cursor=HAND_CURSOR, padx=14, pady=4).pack(side="right")
        self._rename_btn = tk.Button(fi, text="⟳  Rename Checked Files",
                                     command=self._do_rename,
                                     bg=_T["accent"], fg=_T["bg"],
                                     relief="flat", font=("Segoe UI", 9, "bold"),
                                     cursor=HAND_CURSOR, padx=14, pady=4)
        self._rename_btn.pack(side="right", padx=(0, 8))

    def _add_row(self, entry: dict, idx: int):
        bg      = _T["bg_card"] if idx % 2 == 0 else _T["bg"]
        cands   = entry["candidates"]
        quality = entry["quality"]

        row = tk.Frame(self._rows_frame, bg=bg,
                       highlightthickness=1, highlightbackground=_T["border"])
        row.pack(fill="x", pady=(0, 1))
        entry["row_frame"] = row

        inner = tk.Frame(row, bg=bg)
        inner.pack(fill="x", padx=14, pady=8)

        # Checkbox
        chk = tk.Checkbutton(inner, variable=entry["check_var"],
                             bg=bg, activebackground=bg,
                             selectcolor="#ffffff",
                             command=self._update_summary)
        chk.pack(side="left")
        if not cands:
            chk.config(state="disabled")
            entry["check_var"].set(False)

        # Current filename — coloured by quality
        fname   = entry["item"]["filename"]
        display = fname if len(fname) <= 38 else fname[:35] + "…"
        fg_col  = _T["danger"] if quality == "missing_tid" else _T["purple"]
        tk.Label(inner, text=display, width=38, anchor="w",
                 font=("Segoe UI", 9),
                 fg=fg_col if cands else _T["text_muted"],
                 bg=bg).pack(side="left", padx=(6, 0))

        # Arrow
        tk.Label(inner, text="→", font=("Segoe UI", 10),
                 fg=_T["text_muted"], bg=bg,
                 width=2, anchor="center").pack(side="left", padx=(4, 0))

        if cands:
            # Combobox of DB matches — include DB size and match indicator
            actual_size = entry.get("actual_size", 0)
            def _combo_label(name, tid, cand_entry):
                db_size = cand_entry.get("size") or 0
                size_str = f"  {_fmt_size(db_size)}" if db_size else ""
                if actual_size and db_size:
                    ratio = actual_size / db_size if db_size > actual_size else db_size / actual_size
                    size_str += "  ✓" if ratio >= 0.85 else ("  ~" if ratio >= 0.5 else "  ✗")
                return f"{name}  [{tid.upper()}]{size_str}"
            combo_values = [_combo_label(name, tid, e) for _, name, tid, e in cands]
            combo = ttk.Combobox(inner, values=combo_values, state="readonly",
                                 width=34, font=("Segoe UI", 9))
            combo.current(0)
            combo.pack(side="left", padx=(4, 0))
            entry["combo"] = combo

            def _on_pick(event, e=entry):
                e["sel_idx"].set(e["combo"].current())
                self._refresh_proposed(e)
                self._update_summary()

            combo.bind("<<ComboboxSelected>>", _on_pick)

            # Proposed filename entry (auto-updated from combobox, user-editable)
            prop_entry = tk.Entry(inner, textvariable=entry["prop_var"],
                                  font=("Segoe UI", 9),
                                  bg=_T["bg_hover"], fg=_T["text"],
                                  relief="solid", bd=1,
                                  insertbackground=_T["accent"])
            prop_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))

            # Region hint badge if one was found
            if entry["region_hint"]:
                tk.Label(inner, text=f"hint: {entry['region_hint']}",
                         font=("Segoe UI", 7), fg=_T["text_muted"],
                         bg=bg, padx=4).pack(side="right")
        else:
            hint = entry["search_name"] or fname
            tk.Label(inner,
                     text=f'No DB match found  (searched: "{hint[:48]}")',
                     anchor="w", font=("Segoe UI", 9, "italic"),
                     fg=_T["text_muted"], bg=bg).pack(side="left", padx=(8, 0))

    def _on_wheel(self, event):
        self._canvas.yview_scroll(-1 * (event.delta // 120), "units")

    # ── filter ─────────────────────────────────────────────────────────────

    def _visible_entries(self) -> list:
        q = self._search_var.get().lower()
        if not q:
            return list(self._plan)
        return [e for e in self._plan if q in e["item"]["filename"].lower()]

    def _apply_filter(self, *_):
        visible_ids = {id(e) for e in self._visible_entries()}
        for entry in self._plan:
            frame = entry.get("row_frame")
            if frame is None:
                continue
            if id(entry) in visible_ids:
                frame.pack(fill="x", pady=(0, 1))
            else:
                frame.pack_forget()
        self._rows_frame.event_generate("<Configure>")
        self._update_summary()

    # ── controls ───────────────────────────────────────────────────────────

    def _select_all(self):
        for e in self._visible_entries():
            if e["candidates"]:
                e["check_var"].set(True)
        self._update_summary()

    def _deselect_all(self):
        for e in self._visible_entries():
            e["check_var"].set(False)
        self._update_summary()

    def _update_summary(self):
        visible = self._visible_entries()
        checked = sum(1 for e in visible if e["check_var"].get())
        matched = sum(1 for e in visible if e["candidates"])
        no_match = len(visible) - matched
        total = len(self._plan)
        parts = [f"{checked} of {matched} selected for rename"]
        if len(visible) < total:
            parts.append(f"{len(visible)} of {total} shown")
        if no_match:
            parts.append(f"{no_match} no DB match")
        self._summary_lbl.config(text="  •  ".join(parts))

    # ── rename ─────────────────────────────────────────────────────────────

    def _do_rename(self):
        to_rename = [e for e in self._visible_entries()
                     if e["check_var"].get() and e["candidates"]]
        if not to_rename:
            messagebox.showinfo("Nothing to do",
                                "No files are checked for renaming.", parent=self)
            return

        ok, skip, errors = 0, 0, []
        completed_batch = []

        for entry in to_rename:
            item     = entry["item"]
            filepath = item.get("filepath", "")
            proposed = entry["prop_var"].get().strip()

            if not filepath or not proposed:
                skip += 1
                continue

            new_path = os.path.join(os.path.dirname(filepath), proposed)
            if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(filepath):
                errors.append(f"Skipped (target exists): {proposed}")
                skip += 1
                continue

            try:
                os.rename(filepath, new_path)
                completed_batch.append((new_path, filepath))
                ok += 1
            except OSError as exc:
                errors.append(f"{item['filename']}: {exc}")
                skip += 1

        msg = f"Renamed: {ok}"
        if skip:
            msg += f"  |  Skipped / errors: {skip}"
        if errors:
            msg += "\n\nDetails:\n" + "\n".join(errors[:15])
            messagebox.showwarning("Rename Complete", msg, parent=self)
        else:
            messagebox.showinfo("Rename Complete", msg, parent=self)

        if ok:
            self._parent.push_rename_batch(completed_batch)
            self.destroy()
            self._parent.scan()
