"""
ui/mirror_dialog.py — Database mirror selection dialog.

Lets the user choose between named mirror presets or supply a custom
base URL.  Selection is persisted to ~/.nxlibrarian_config.ini.
"""

import configparser
import tkinter as tk
from tkinter import messagebox
import requests

from constants import (
    CONFIG_FILE, DB_MIRRORS, DEFAULT_MIRROR, HAND_CURSOR, get_db_urls,
)

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

_DESCRIPTIONS = {
    "GitHub (Primary)": (
        "raw.githubusercontent.com\n"
        "The official blawar/titledb repository served directly from GitHub.\n"
        "Most up-to-date but can be slow or rate-limited outside the US."
    ),
    "jsDelivr CDN": (
        "cdn.jsdelivr.net\n"
        "Global CDN that automatically mirrors any public GitHub repo.\n"
        "Usually faster internationally and rarely goes down independently."
    ),
    "Custom": (
        "Enter any base URL below.\n"
        "The app will append versions.json, cnmts.json, and regional\n"
        "JSON files (US.en.json, GB.en.json, etc.) to the URL you provide."
    ),
}


def show_mirror_dialog(parent):
    MirrorDialog(parent)


class MirrorDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Database Mirror")
        self.resizable(False, False)
        self.configure(bg=_T["bg"])
        self.transient(parent)

        # Load current settings
        cfg = configparser.ConfigParser()
        cfg.read(CONFIG_FILE)
        self._sel   = tk.StringVar(value=cfg.get("Settings", "db_mirror",        fallback=DEFAULT_MIRROR))
        self._custom = tk.StringVar(value=cfg.get("Settings", "db_mirror_custom", fallback=""))

        self._build_ui()

        self.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x  = px + (pw - self.winfo_width())  // 2
        y  = py + (ph - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        self.grab_set()

    def _build_ui(self):
        from constants import UI_FONT, FONT_BOOST
        _F = FONT_BOOST

        # Title bar
        hdr = tk.Frame(self, bg=_T["bg_card"],
                       highlightthickness=1, highlightbackground=_T["border"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚙  DATABASE MIRROR",
                 font=(UI_FONT, 13 + _F, "bold"),
                 fg=_T["text"], bg=_T["bg_card"],
                 padx=20, pady=14).pack(side="left")

        body = tk.Frame(self, bg=_T["bg"], padx=24, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(body,
                 text="Choose where NX-Librarian fetches the title database from.\n"
                      "If the primary source is down, the app will automatically\n"
                      "try the other named mirrors as a fallback.",
                 font=(UI_FONT, 9 + _F), fg=_T["text_dim"], bg=_T["bg"],
                 justify="left").pack(anchor="w", pady=(0, 16))

        # Radio buttons for each mirror
        self._desc_lbl = None
        for name in DB_MIRRORS:
            row = tk.Frame(body, bg=_T["bg_card"],
                           highlightthickness=1, highlightbackground=_T["border"])
            row.pack(fill="x", pady=(0, 6))
            ri = tk.Frame(row, bg=_T["bg_card"])
            ri.pack(fill="x", padx=12, pady=10)

            rb = tk.Radiobutton(
                ri, text=name, variable=self._sel, value=name,
                font=(UI_FONT, 10 + _F, "bold"),
                fg=_T["text"], bg=_T["bg_card"],
                activebackground=_T["bg_card"], activeforeground=_T["accent"],
                selectcolor=_T["bg_hover"],
                cursor=HAND_CURSOR,
                command=self._on_select)
            rb.pack(anchor="w")

            desc = _DESCRIPTIONS.get(name, "")
            if desc:
                lines = desc.split("\n", 1)
                tk.Label(ri, text=lines[0],
                         font=(UI_FONT, 8 + _F, "bold"),
                         fg=_T["accent"], bg=_T["bg_card"],
                         justify="left").pack(anchor="w", padx=(20, 0))
                if len(lines) > 1:
                    tk.Label(ri, text=lines[1],
                             font=(UI_FONT, 8 + _F),
                             fg=_T["text_muted"], bg=_T["bg_card"],
                             justify="left").pack(anchor="w", padx=(20, 0))

        # Custom URL entry (only active when Custom is selected)
        cust_frame = tk.Frame(body, bg=_T["bg"])
        cust_frame.pack(fill="x", pady=(4, 0))
        tk.Label(cust_frame, text="Custom base URL:",
                 font=(UI_FONT, 9 + _F), fg=_T["text_dim"],
                 bg=_T["bg"]).pack(side="left", padx=(0, 8))
        self._custom_entry = tk.Entry(
            cust_frame, textvariable=self._custom,
            font=(UI_FONT, 9 + _F),
            bg=_T["bg_hover"], fg=_T["text"],
            insertbackground=_T["accent"],
            relief="solid", bd=1, width=44)
        self._custom_entry.pack(side="left", fill="x", expand=True)

        # Test + status
        test_row = tk.Frame(body, bg=_T["bg"])
        test_row.pack(fill="x", pady=(8, 0))
        self._test_btn = tk.Button(
            test_row, text="⚡ Test Connection",
            command=self._test_connection,
            bg=_T["border_lt"], fg=_T["text_dim"],
            relief="flat", font=(UI_FONT, 9 + _F),
            cursor=HAND_CURSOR, padx=10, pady=4)
        self._test_btn.pack(side="left")
        self._status_lbl = tk.Label(
            test_row, text="", font=(UI_FONT, 8 + _F),
            fg=_T["text_dim"], bg=_T["bg"])
        self._status_lbl.pack(side="left", padx=(12, 0))

        # Footer
        footer = tk.Frame(self, bg=_T["bg_card"],
                          highlightthickness=1, highlightbackground=_T["border"])
        footer.pack(fill="x", side="bottom")
        fi = tk.Frame(footer, bg=_T["bg_card"])
        fi.pack(fill="x", padx=16, pady=12)

        tk.Button(fi, text="Cancel", command=self.destroy,
                  bg=_T["border_lt"], fg=_T["text_dim"],
                  relief="flat", font=(UI_FONT, 9 + _F, "bold"),
                  cursor=HAND_CURSOR, padx=14, pady=4).pack(side="right")
        tk.Button(fi, text="✓  Save", command=self._save,
                  bg=_T["accent"], fg=_T["bg"],
                  relief="flat", font=(UI_FONT, 9 + _F, "bold"),
                  cursor=HAND_CURSOR, padx=14, pady=4).pack(side="right", padx=(0, 8))

        self._on_select()   # set initial state of custom entry

    def _on_select(self):
        is_custom = self._sel.get() == "Custom"
        self._custom_entry.config(
            state="normal" if is_custom else "disabled",
            fg=_T["text"] if is_custom else _T["text_muted"])
        self._status_lbl.config(text="")

    def _test_connection(self):
        sel = self._sel.get()
        if sel == "Custom":
            base = self._custom.get().strip()
            if not base:
                self._status_lbl.config(text="Enter a URL first.", fg=_T["warn"])
                return
            urls = get_db_urls(base)
        else:
            urls = get_db_urls(DB_MIRRORS[sel])

        self._status_lbl.config(text="Testing…", fg=_T["text_dim"])
        self.update_idletasks()
        try:
            r = requests.get(urls["versions"], timeout=8)
            r.raise_for_status()
            size = len(r.content)
            self._status_lbl.config(
                text=f"✓ Connected  ({size // 1024} KB received)",
                fg=_T["ok"])
        except Exception as exc:
            self._status_lbl.config(
                text=f"✗ Failed: {exc}",
                fg=_T["danger"])

    def _save(self):
        sel = self._sel.get()
        if sel == "Custom" and not self._custom.get().strip():
            messagebox.showwarning(
                "Custom URL Required",
                "Please enter a base URL for the custom mirror.",
                parent=self)
            return

        cfg = configparser.ConfigParser()
        cfg.read(CONFIG_FILE)
        if "Settings" not in cfg:
            cfg["Settings"] = {}
        cfg["Settings"]["db_mirror"]        = sel
        cfg["Settings"]["db_mirror_custom"] = self._custom.get().strip()
        with open(CONFIG_FILE, "w") as f:
            cfg.write(f)

        self.destroy()
        messagebox.showinfo(
            "Mirror Saved",
            f"Database mirror set to: {sel}\n\n"
            "The new mirror will be used on the next database sync.",
            parent=self.master)
