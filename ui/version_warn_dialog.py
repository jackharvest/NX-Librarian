"""
ui/version_warn_dialog.py — Warning dialog for base game files with version > 0.

Presents a two-panel "this or that" choice styled exactly like the mode-select
screen: red panel (Override to v0) vs blue panel (Migrate to Updates folder).
Analyses file size vs DB expected size to surface a recommended action.
"""

import os
import re
import configparser
import tkinter as tk
from tkinter import filedialog, messagebox

from constants import UI_FONT, FONT_BOOST, HAND_CURSOR, CONFIG_FILE

_F = FONT_BOOST

_PANELS = {
    "override": {
        "emoji": "🔧",
        "title": "OVERRIDE TO v0",
        "sub":   "Rename as Base Game",
        "bg":    "#B8000F",
        "bg_h":  "#F0001A",
    },
    "migrate": {
        "emoji": "📦",
        "title": "MIGRATE TO UPDATES",
        "sub":   "Move to Updates Folder",
        "bg":    "#0050A8",
        "bg_h":  "#0077FF",
    },
    "strip_tag": {
        "emoji": "✂️",
        "title": "STRIP BASE TAG",
        "sub":   "Remove [Base] from Filename",
        "bg":    "#B8000F",
        "bg_h":  "#F0001A",
    },
    "to_base": {
        "emoji": "🎮",
        "title": "MIGRATE TO BASE",
        "sub":   "Move to Base Games Folder",
        "bg":    "#0050A8",
        "bg_h":  "#0077FF",
    },
}


def _fmt_size(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_073_741_824:.1f} GB"
    if n >= 1_000_000:
        return f"{n / 1_048_576:.1f} MB"
    return f"{n // 1024} KB"


class _ChoicePanel(tk.Frame):
    """Colour panel matching the mode-select aesthetic."""

    def __init__(self, parent, cfg, on_click, suggested=False, reason="", **kwargs):
        super().__init__(parent, bg=cfg["bg"], cursor=HAND_CURSOR, **kwargs)
        self._bg        = cfg["bg"]
        self._bg_h      = cfg["bg_h"]
        self._widgets   = []
        self._sublbls   = []
        self._suggested = suggested
        self._reason    = reason
        self._build(cfg, on_click)

    def _reg(self, w, is_sub=False):
        self._widgets.append(w)
        if is_sub:
            self._sublbls.append(w)
        return w

    def _build(self, cfg, on_click):
        self._reg(self)
        # Top spacer
        self._reg(tk.Frame(self, bg=self._bg, cursor=HAND_CURSOR)).pack(
            fill="both", expand=True)
        # Content block
        c = self._reg(tk.Frame(self, bg=self._bg, cursor=HAND_CURSOR))
        c.pack(fill="x", padx=24)

        self._reg(tk.Label(c, text=cfg["emoji"],
                           font=("Arial", 52 + _F * 2),
                           bg=self._bg, cursor=HAND_CURSOR)).pack(anchor="center")

        self._reg(tk.Label(c, text=cfg["title"],
                           font=(UI_FONT, 17 + _F, "bold"),
                           fg="#ffffff", bg=self._bg,
                           cursor=HAND_CURSOR)).pack(anchor="center", pady=(14, 0))

        self._reg(tk.Label(c, text=cfg["sub"],
                           font=(UI_FONT, 10 + _F),
                           fg="#aaaaaa", bg=self._bg,
                           cursor=HAND_CURSOR),
                  is_sub=True).pack(anchor="center", pady=(6, 0))

        if self._suggested:
            self._reg(tk.Label(c, text="✦  SUGGESTED",
                               font=(UI_FONT, 9 + _F, "bold"),
                               fg="#fbbf24", bg=self._bg,
                               cursor=HAND_CURSOR)).pack(anchor="center", pady=(14, 0))
            if self._reason:
                self._reg(tk.Label(c, text=f"Why: {self._reason}",
                                   font=(UI_FONT, 8 + _F),
                                   fg="#ffffff", bg=self._bg,
                                   cursor=HAND_CURSOR,
                                   wraplength=220, justify="center"
                                   )).pack(anchor="center", pady=(4, 0))

        # Bottom spacer
        self._reg(tk.Frame(self, bg=self._bg, cursor=HAND_CURSOR)).pack(
            fill="both", expand=True)

        for w in self._widgets:
            try:
                w.bind("<Button-1>", lambda e: on_click())
                w.bind("<Enter>",    lambda e: self._hover(True))
                w.bind("<Leave>",    lambda e: self._on_leave(e))
            except Exception:
                pass

    def _hover(self, on):
        bg = self._bg_h if on else self._bg
        for w in self._widgets:
            try:
                w.config(bg=bg)
            except Exception:
                pass
        fg_sub = "#ffffff" if on else "#aaaaaa"
        for w in self._sublbls:
            try:
                w.config(fg=fg_sub)
            except Exception:
                pass

    def _on_leave(self, event):
        try:
            px, py = self.winfo_rootx(), self.winfo_rooty()
            pw, ph = self.winfo_width(), self.winfo_height()
            if not (px <= event.x_root <= px + pw and
                    py <= event.y_root <= py + ph):
                self._hover(False)
        except Exception:
            self._hover(False)


class VersionWarnDialog(tk.Toplevel):
    """
    Modal warning for a base-game file whose version > 0.

    Analyses actual file size vs DB expected v0 size to recommend an action.
    """

    def __init__(self, parent_screen, item: dict, norm_t: dict = None):
        super().__init__(parent_screen)
        self._parent = parent_screen
        self._item   = item
        self._norm_t = norm_t or {}

        self.title("Version Warning")
        self.geometry("760x540")
        self.resizable(False, False)
        self.configure(bg="#0a0a14")
        self.transient(parent_screen)

        self._suggestion, self._reason = self._compute_suggestion()
        self._build_ui()

        self.update_idletasks()
        px, py = parent_screen.winfo_rootx(), parent_screen.winfo_rooty()
        pw, ph = parent_screen.winfo_width(), parent_screen.winfo_height()
        self.geometry(
            f"+{px + (pw - self.winfo_width()) // 2}"
            f"+{py + (ph - self.winfo_height()) // 2}")
        self.grab_set()

    # ------------------------------------------------------------------
    # Suggestion logic
    # ------------------------------------------------------------------

    def _compute_suggestion(self):
        """Return ('override'|'migrate'|None, reason_str) based on file size."""
        filepath = self._item.get("filepath", "")
        tid      = self._item.get("tid", "").lower()

        actual_size = 0
        try:
            if filepath:
                actual_size = os.path.getsize(filepath)
        except OSError:
            pass

        db_entry = self._norm_t.get(tid, {})
        db_size  = db_entry.get("size") or 0

        if not actual_size or not db_size:
            return None, ""

        actual_str = _fmt_size(actual_size)
        db_str     = _fmt_size(db_size)
        ratio      = actual_size / db_size  # can be > 1 if file is larger than base game

        if 0.85 <= ratio <= 1.15:
            # File is within ~15% of the base game size — likely mislabelled base
            return ("override",
                    f"File is {actual_str} — closely matches the expected "
                    f"base game size of {db_str}. Looks like a correctly-sized "
                    f"base game with a wrong version tag.")
        elif ratio < 0.5:
            # Much smaller than base — classic update/patch
            return ("migrate",
                    f"File is {actual_str} — much smaller than the expected "
                    f"base game size of {db_str}. Consistent with an update "
                    f"patch, not the full game.")
        elif ratio > 1.15:
            # Larger than the base game — could be a fat update bundle or wrong match
            return ("migrate",
                    f"File is {actual_str} — larger than the expected base game "
                    f"size of {db_str}. This may be an update or a different edition.")
        else:
            # Ambiguous middle ground
            return ("migrate",
                    f"File is {actual_str} vs expected base game size of {db_str}. "
                    f"The size difference suggests this may be an update file.")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        fname = self._item.get("filename", "")
        ver   = self._item.get("version", 0)

        # ── Red warning header ──────────────────────────────────────────
        header = tk.Frame(self, bg="#B8000F")
        header.pack(fill="x")
        tk.Label(header, text="⚠   VERSION WARNING",
                 font=(UI_FONT, 13 + _F, "bold"),
                 fg="#ffffff", bg="#B8000F",
                 padx=24, pady=14).pack(side="left")

        # ── File info card ──────────────────────────────────────────────
        card = tk.Frame(self, bg="#151d33",
                        highlightthickness=1, highlightbackground="#2a3f5f")
        card.pack(fill="x", padx=20, pady=(16, 0))
        ci = tk.Frame(card, bg="#151d33")
        ci.pack(fill="x", padx=20, pady=14)

        display_name = fname if len(fname) <= 72 else fname[:69] + "…"
        tk.Label(ci, text=display_name,
                 font=(UI_FONT, 9 + _F),
                 fg="#9ca3af", bg="#151d33",
                 anchor="w").pack(fill="x")

        tk.Label(ci,
                 text=f"Version v{ver} was found in the Base Game library — "
                      f"base games should always be v0.\n"
                      f"This file may be an update that ended up in the wrong folder.",
                 font=(UI_FONT, 10 + _F),
                 fg="#f97316", bg="#151d33",
                 anchor="w", justify="left", wraplength=700).pack(fill="x", pady=(8, 0))

        # ── Two-panel choice ────────────────────────────────────────────
        choice = tk.Frame(self, bg="#000000")
        choice.pack(fill="both", expand=True, padx=20, pady=16)
        choice.columnconfigure(0, weight=1, uniform="ch")
        choice.columnconfigure(1, weight=1, uniform="ch")
        choice.rowconfigure(0, weight=1)

        _ChoicePanel(choice, _PANELS["override"], self._do_override,
                     suggested=(self._suggestion == "override"),
                     reason=self._reason if self._suggestion == "override" else ""
                     ).grid(row=0, column=0, sticky="nsew", padx=(0, 2))

        _ChoicePanel(choice, _PANELS["migrate"], self._do_migrate,
                     suggested=(self._suggestion == "migrate"),
                     reason=self._reason if self._suggestion == "migrate" else ""
                     ).grid(row=0, column=1, sticky="nsew")

        # ── Cancel ──────────────────────────────────────────────────────
        footer = tk.Frame(self, bg="#0a0a14")
        footer.pack(fill="x", padx=20, pady=(0, 14))
        cancel = tk.Label(footer, text="Cancel", bg="#0a0a14",
                          fg="#6b7280", font=(UI_FONT, 9 + _F), cursor=HAND_CURSOR)
        cancel.pack(side="right")
        cancel.bind("<Button-1>", lambda e: self.destroy())
        cancel.bind("<Enter>",    lambda e: cancel.config(fg="#9ca3af"))
        cancel.bind("<Leave>",    lambda e: cancel.config(fg="#6b7280"))
        self.bind("<Escape>", lambda e: self.destroy())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _do_override(self):
        """Rename [vXXXX] → [v0] in place."""
        item     = self._item
        filepath = item.get("filepath", "")
        fname    = item.get("filename", "")
        folder   = os.path.dirname(filepath)

        new_name = re.sub(r'\[v\d+\]', '[v0]', fname, flags=re.IGNORECASE)
        if new_name == fname:
            stem, ext = os.path.splitext(fname)
            new_name = f"{stem}[v0]{ext}"

        new_path = os.path.join(folder, new_name)
        if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(filepath):
            messagebox.showerror("Cannot Rename",
                f"A file named '{new_name}' already exists in this folder.",
                parent=self)
            return

        try:
            os.rename(filepath, new_path)
            self._parent.push_rename_batch([(new_path, filepath)])
            self.destroy()
            self._parent.scan()
        except OSError as exc:
            messagebox.showerror("Rename Failed", str(exc), parent=self)

    def _do_migrate(self):
        """Move the file to the updates folder."""
        updates_folder = ""
        try:
            cfg = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                cfg.read(CONFIG_FILE)
                updates_folder = cfg.get("Folders", "folder_updates", fallback="")
        except Exception:
            pass

        if not updates_folder or not os.path.isdir(updates_folder):
            updates_folder = filedialog.askdirectory(
                title="Select Updates Folder to migrate into", parent=self)
            if not updates_folder:
                return

        item     = self._item
        filepath = item.get("filepath", "")
        fname    = item.get("filename", "")
        new_path = os.path.join(updates_folder, fname)

        if os.path.exists(new_path):
            messagebox.showerror("Cannot Move",
                f"'{fname}' already exists in the updates folder.",
                parent=self)
            return

        try:
            os.rename(filepath, new_path)
            self._parent.push_rename_batch([(new_path, filepath)])
            self.destroy()
            self._parent.scan()
        except OSError as exc:
            messagebox.showerror("Move Failed", str(exc), parent=self)


class BaseMisplacedDialog(tk.Toplevel):
    """
    Modal warning for an updates-folder file that appears to be a base game
    (version == 0 or filename contains [Base]).

    Analyses actual file size vs DB expected v0 size to recommend:
      - MIGRATE TO BASE  (blue) — file size ≈ base game → it IS the base game
      - STRIP BASE TAG   (red)  — file is small/patch-sized → remove [Base] tag
    """

    def __init__(self, parent_screen, item: dict, norm_t: dict = None):
        super().__init__(parent_screen)
        self._parent = parent_screen
        self._item   = item
        self._norm_t = norm_t or {}

        self.title("Base Game Warning")
        self.geometry("760x540")
        self.resizable(False, False)
        self.configure(bg="#0a0a14")
        self.transient(parent_screen)

        self._suggestion, self._reason = self._compute_suggestion()
        self._build_ui()

        self.update_idletasks()
        px, py = parent_screen.winfo_rootx(), parent_screen.winfo_rooty()
        pw, ph = parent_screen.winfo_width(), parent_screen.winfo_height()
        self.geometry(
            f"+{px + (pw - self.winfo_width()) // 2}"
            f"+{py + (ph - self.winfo_height()) // 2}")
        self.grab_set()

    # ------------------------------------------------------------------
    # Suggestion logic
    # ------------------------------------------------------------------

    def _compute_suggestion(self):
        """Return ('to_base'|'strip_tag'|None, reason_str) based on file size."""
        filepath = self._item.get("filepath", "")
        tid      = self._item.get("tid", "").lower()
        # Try base TID for DB lookup (updates folder files have base TID in item)
        base_tid = tid[:13] + "000" if len(tid) == 16 else tid

        actual_size = 0
        try:
            if filepath:
                actual_size = os.path.getsize(filepath)
        except OSError:
            pass

        db_entry = self._norm_t.get(base_tid) or self._norm_t.get(tid) or {}
        db_size  = db_entry.get("size") or 0

        if not actual_size or not db_size:
            return None, ""

        actual_str = _fmt_size(actual_size)
        db_str     = _fmt_size(db_size)
        ratio      = actual_size / db_size

        if 0.85 <= ratio <= 1.15:
            return ("to_base",
                    f"File is {actual_str} — closely matches the expected "
                    f"base game size of {db_str}. This looks like the real "
                    f"base game that ended up in the wrong folder.")
        elif ratio < 0.5:
            return ("strip_tag",
                    f"File is {actual_str} — much smaller than the expected "
                    f"base game size of {db_str}. Likely an update/patch with "
                    f"a misleading [Base] tag.")
        elif ratio > 1.15:
            return ("strip_tag",
                    f"File is {actual_str} — larger than the expected base game "
                    f"size of {db_str}. Base games are consistently sized; this "
                    f"is likely an update bundle with a misleading [Base] tag.")
        else:
            return ("strip_tag",
                    f"File is {actual_str} vs expected base game size of {db_str}. "
                    f"The size difference suggests this may not be the base game.")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        fname = self._item.get("filename", "")

        # ── Amber warning header ─────────────────────────────────────────
        header = tk.Frame(self, bg="#92400e")
        header.pack(fill="x")
        tk.Label(header, text="⚠   BASE GAME WARNING",
                 font=(UI_FONT, 13 + _F, "bold"),
                 fg="#ffffff", bg="#92400e",
                 padx=24, pady=14).pack(side="left")

        # ── File info card ───────────────────────────────────────────────
        card = tk.Frame(self, bg="#151d33",
                        highlightthickness=1, highlightbackground="#2a3f5f")
        card.pack(fill="x", padx=20, pady=(16, 0))
        ci = tk.Frame(card, bg="#151d33")
        ci.pack(fill="x", padx=20, pady=14)

        display_name = fname if len(fname) <= 72 else fname[:69] + "…"
        tk.Label(ci, text=display_name,
                 font=(UI_FONT, 9 + _F),
                 fg="#9ca3af", bg="#151d33",
                 anchor="w").pack(fill="x")

        tk.Label(ci,
                 text="This file is in the Updates folder but appears to be v0 or tagged [Base].\n"
                      "It may be a base game in the wrong folder, or an update with a bad tag.",
                 font=(UI_FONT, 10 + _F),
                 fg="#fbbf24", bg="#151d33",
                 anchor="w", justify="left", wraplength=700).pack(fill="x", pady=(8, 0))

        # ── Two-panel choice ─────────────────────────────────────────────
        choice = tk.Frame(self, bg="#000000")
        choice.pack(fill="both", expand=True, padx=20, pady=16)
        choice.columnconfigure(0, weight=1, uniform="ch")
        choice.columnconfigure(1, weight=1, uniform="ch")
        choice.rowconfigure(0, weight=1)

        _ChoicePanel(choice, _PANELS["strip_tag"], self._do_strip_tag,
                     suggested=(self._suggestion == "strip_tag"),
                     reason=self._reason if self._suggestion == "strip_tag" else ""
                     ).grid(row=0, column=0, sticky="nsew", padx=(0, 2))

        _ChoicePanel(choice, _PANELS["to_base"], self._do_migrate_to_base,
                     suggested=(self._suggestion == "to_base"),
                     reason=self._reason if self._suggestion == "to_base" else ""
                     ).grid(row=0, column=1, sticky="nsew")

        # ── Cancel ───────────────────────────────────────────────────────
        footer = tk.Frame(self, bg="#0a0a14")
        footer.pack(fill="x", padx=20, pady=(0, 14))
        cancel = tk.Label(footer, text="Cancel", bg="#0a0a14",
                          fg="#6b7280", font=(UI_FONT, 9 + _F), cursor=HAND_CURSOR)
        cancel.pack(side="right")
        cancel.bind("<Button-1>", lambda e: self.destroy())
        cancel.bind("<Enter>",    lambda e: cancel.config(fg="#9ca3af"))
        cancel.bind("<Leave>",    lambda e: cancel.config(fg="#6b7280"))
        self.bind("<Escape>", lambda e: self.destroy())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _do_strip_tag(self):
        """Remove [Base] / [BASE] / [base] from the filename in place."""
        item     = self._item
        filepath = item.get("filepath", "")
        fname    = item.get("filename", "")
        folder   = os.path.dirname(filepath)

        new_name = re.sub(r'\[(?:Base|BASE|base)\]', '', fname).strip()
        # Clean up any double spaces left behind
        new_name = re.sub(r'  +', ' ', new_name)
        if new_name == fname:
            messagebox.showinfo("Nothing to Strip",
                "No [Base] tag was found in the filename.", parent=self)
            return

        new_path = os.path.join(folder, new_name)
        if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(filepath):
            messagebox.showerror("Cannot Rename",
                f"A file named '{new_name}' already exists in this folder.",
                parent=self)
            return

        try:
            os.rename(filepath, new_path)
            self._parent.push_rename_batch([(new_path, filepath)])
            self.destroy()
            self._parent.scan()
        except OSError as exc:
            messagebox.showerror("Rename Failed", str(exc), parent=self)

    def _do_migrate_to_base(self):
        """Move the file to the base games folder."""
        base_folder = ""
        try:
            cfg = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                cfg.read(CONFIG_FILE)
                base_folder = cfg.get("Folders", "folder_base", fallback="")
        except Exception:
            pass

        if not base_folder or not os.path.isdir(base_folder):
            base_folder = filedialog.askdirectory(
                title="Select Base Games Folder to migrate into", parent=self)
            if not base_folder:
                return

        item     = self._item
        filepath = item.get("filepath", "")
        fname    = item.get("filename", "")
        new_path = os.path.join(base_folder, fname)

        if os.path.exists(new_path):
            messagebox.showerror("Cannot Move",
                f"'{fname}' already exists in the base games folder.",
                parent=self)
            return

        try:
            os.rename(filepath, new_path)
            self._parent.push_rename_batch([(new_path, filepath)])
            self.destroy()
            self._parent.scan()
        except OSError as exc:
            messagebox.showerror("Move Failed", str(exc), parent=self)
