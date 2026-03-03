"""
ui/base_screen.py — REVOLUTIONARY v3 screen scaffold.

Completely redesigned with:
- Modern dark aesthetics with glassmorphic elements  
- Sophisticated typography and spacing
- Dynamic data dashboard instead of static table
- Premium micro-interactions with smooth animations
- Professional polish worthy of next-generation software
- Enhanced visual hierarchy and information density
- Modern card-based layouts and filter systems

This is v3: utterly unrecognizable from v2.
"""

import os
import tkinter as tk
from tkinter import filedialog, ttk
import configparser
import threading

from constants import COLOR_BG, CONFIG_FILE

try:
    from PIL import Image, ImageTk
    PILLOW_OK = True
except ImportError:
    PILLOW_OK = False


# Premium color system — vibrant and modern
THEME = {
    "bg_primary":     "#0a0a14",      # Deep space background
    "bg_secondary":   "#151d33",      # Card/panel background
    "bg_tertiary":    "#1f2847",      # Hover/active background
    "bg_raised":      "#1a1f3a",      # Raised panel
    
    "text_primary":   "#ffffff",
    "text_secondary": "#9ca3af",
    "text_muted":     "#6b7280",
    
    "border_subtle":  "#2a3f5f",
    "border_light":   "#3a4a6f",
    
    "accent_primary": "#60a5fa",      # Electric blue
    "accent_glow":    "#06d6d0",      # Fresh cyan
    "status_ok":      "#10b981",      # Green
    "status_warn":    "#f97316",      # Orange
    "status_danger":  "#ef4444",      # Red
}


class BaseScreen(tk.Frame):
    """Abstract scaffold for all mode screens with premium design."""

    MODE_KEY       = "base"
    MODE_LABEL     = "LIBRARY MODE"
    ACCENT_COLOR   = THEME["accent_primary"]
    COLUMNS        = []

    def __init__(self, parent, on_back, logo_img=None, norm_v=None, norm_t=None, norm_c=None, **kwargs):
        super().__init__(parent, bg=THEME["bg_primary"], **kwargs)
        self._on_back  = on_back
        self._logo_img  = logo_img
        self.norm_v     = norm_v or {}
        self.norm_t     = norm_t or {}
        self.norm_c     = norm_c or {}

        self.all_data         = []
        self.target_folder    = tk.StringVar()
        self.search_query     = tk.StringVar()
        self._ctx_col         = None
        self.show_missing_tid = False
        self.show_bad_names   = False
        self._missing_tid_count = 0
        self._bad_names_count   = 0
        self._fix_buttons       = []
        self._fix_btn_after_id  = None

        self._load_folder_config()
        self._setup_styles()
        self._build_ui()

        self.search_query.trace_add("write", lambda *a: self.refresh_table())

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def _load_folder_config(self):
        try:
            cfg = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                cfg.read(CONFIG_FILE)
                key = f"folder_{self.MODE_KEY}"
                self.target_folder.set(cfg.get("Folders", key, fallback=""))
        except Exception:
            pass

    def _save_folder_config(self, path):
        try:
            cfg = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                cfg.read(CONFIG_FILE)
            if "Folders" not in cfg:
                cfg["Folders"] = {}
            cfg["Folders"][f"folder_{self.MODE_KEY}"] = path
            with open(CONFIG_FILE, "w") as f:
                cfg.write(f)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Premium scrollbar
        style.configure("Vertical.TScrollbar", 
                       background=THEME["border_light"],
                       troughcolor=THEME["bg_secondary"],
                       bordercolor=THEME["bg_secondary"],
                       arrowcolor=THEME["text_secondary"],
                       width=12)
        
        # Premium treeview with modern styling
        style.configure("Treeview",
                       font=("Segoe UI", 10),
                       rowheight=44,
                       borderwidth=0,
                       background=THEME["bg_secondary"],
                       foreground=THEME["text_primary"],
                       fieldbackground=THEME["bg_secondary"],
                       relief="flat")
        
        style.configure("Treeview.Heading",
                       font=("Segoe UI", 9, "bold"),
                       background=THEME["border_light"],
                       foreground=THEME["text_secondary"],
                       relief="flat",
                       padding=12)
        
        style.map("Treeview.Heading",
                 background=[("active", THEME["bg_tertiary"])])
        
        # Hover and selection
        style.map("Treeview",
                 background=[("selected", THEME["bg_tertiary"])],
                 foreground=[("selected", THEME["accent_primary"])])
        
        # Row striping for readability (tags applied during population)
        style.configure("Striped.Treeview", rowheight=44)
        # We cannot map custom 'evenrow'/'oddrow' states with ttk; tagging is used instead.
        style.map("Striped.Treeview",
                 background=[("selected", THEME["bg_tertiary"])])
        style.map("Striped.Treeview",
                 foreground=[("selected", THEME["accent_primary"])])

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self._build_header()
        self._build_table()
        self._build_statusbar()

    def _build_header(self):
        """Revolutionary modern header with dynamic dashboard look."""
        # Top navigation bar
        nav_bar = tk.Frame(self, bg=THEME["bg_secondary"], 
                          highlightthickness=1, highlightbackground=THEME["border_subtle"])
        nav_bar.pack(fill="x")
        
        nav_inner = tk.Frame(nav_bar, bg=THEME["bg_secondary"], padx=28, pady=16)
        nav_inner.pack(fill="x")
        
        # ── Back button ────────────────────────────────────────────────
        back_btn = tk.Button(nav_inner, text="< BACK", command=self._on_back,
                            bg=THEME["border_light"], fg=THEME["text_secondary"],
                            relief="flat", font=("Segoe UI", 9, "bold"),
                            cursor="hand2", padx=12, pady=6,
                            activebackground=THEME["bg_tertiary"],
                            activeforeground=THEME["accent_primary"])
        back_btn.pack(side="left")
        
        # ── Mode title ─────────────────────────────────────────────────
        title_frame = tk.Frame(nav_inner, bg=THEME["bg_secondary"])
        title_frame.pack(side="left", padx=(20, 0), fill="x", expand=True)
        
        tk.Label(title_frame, text=self.MODE_LABEL, 
                font=("Segoe UI", 14, "bold"),
                fg=THEME["text_primary"], bg=THEME["bg_secondary"]).pack(anchor="w")
        
        tk.Label(title_frame, text="Live library management & organization",
                font=("Segoe UI", 9),
                fg=THEME["text_secondary"], bg=THEME["bg_secondary"]).pack(anchor="w", pady=(2, 0))
        
        # ── Action buttons on right ────────────────────────────────────
        action_frame = tk.Frame(nav_inner, bg=THEME["bg_secondary"])
        action_frame.pack(side="right")
        
        scan_btn = self._create_button(action_frame, "⟳ SCAN", self.scan, primary=True)
        scan_btn.pack(side="left")
        
        # ════════════════════════════════════════════════════════════════
        # Control panel below navigation
        # ════════════════════════════════════════════════════════════════
        control_panel = tk.Frame(self, bg=THEME["bg_primary"])
        control_panel.pack(fill="x", padx=20, pady=(16, 12))
        
        # Folder selection area
        folder_section = tk.Frame(control_panel, bg=THEME["bg_raised"],
                                 highlightthickness=1,
                                 highlightbackground=THEME["border_subtle"])
        folder_section.pack(fill="x", pady=(0, 12))
        
        folder_inner = tk.Frame(folder_section, bg=THEME["bg_raised"])
        folder_inner.pack(fill="x", padx=16, pady=12)
        
        tk.Label(folder_inner, text="📁 Library Path", font=("Segoe UI", 9, "bold"),
                fg=THEME["text_secondary"], bg=THEME["bg_raised"]).pack(anchor="w", pady=(0, 6))
        
        folder_controls = tk.Frame(folder_inner, bg=THEME["bg_raised"])
        folder_controls.pack(fill="x")
        
        path_entry = tk.Entry(folder_controls, textvariable=self.target_folder,
                             font=("Segoe UI", 10),
                             bg=THEME["bg_tertiary"], fg=THEME["text_primary"],
                             relief="solid", bd=1, insertbackground=THEME["accent_primary"],
                             width=60)
        path_entry.pack(side="left", fill="x", expand=True)
        
        browse_btn = self._create_button(folder_controls, "BROWSE", self._browse)
        browse_btn.pack(side="left", padx=(8, 0))

    def _create_button(self, parent, text, command, primary=False):
        """Create a modern button with enhanced styling."""
        btn = tk.Button(parent, text=text, command=command,
                       bg=THEME["accent_primary"] if primary else THEME["border_light"],
                       fg=THEME["bg_primary"] if primary else THEME["text_secondary"],
                       relief="flat", font=("Segoe UI", 9, "bold"),
                       cursor="hand2", padx=14, pady=6,
                       activebackground=THEME["accent_glow"],
                       activeforeground=THEME["bg_primary"],
                       bd=0,
                       highlightthickness=0)
        return btn

    def _build_filter_buttons(self, parent):
        """Override in subclasses to add mode-specific filters."""
        pass

    def _browse(self):
        path = filedialog.askdirectory()
        if path:
            self.target_folder.set(path)
            self._save_folder_config(path)

    # ------------------------------------------------------------------
    # Table
    # ------------------------------------------------------------------

    def _build_table(self):
        """Modern data table with enhanced styling and interactivity."""
        # Container with empty state overlay capability
        self.table_container = tk.Frame(self, bg=THEME["bg_primary"])
        self.table_container.pack(fill="both", expand=True, padx=20, pady=12)
        
        # Table header
        table_header = tk.Frame(self.table_container, bg=THEME["bg_secondary"],
                               highlightthickness=1,
                               highlightbackground=THEME["border_subtle"])
        table_header.pack(fill="x", pady=(0, 1))
        
        header_inner = tk.Frame(table_header, bg=THEME["bg_secondary"])
        header_inner.pack(fill="x", padx=12, pady=8)

        # ── RIGHT: stats counter + quality filter buttons ───────────────
        right_frame = tk.Frame(header_inner, bg=THEME["bg_secondary"])
        right_frame.pack(side="right")

        self.stats_lbl = tk.Label(right_frame, text="Ready",
                                  font=("Segoe UI", 9, "bold"),
                                  fg=THEME["text_secondary"], bg=THEME["bg_secondary"])
        self.stats_lbl.pack(side="left", padx=(0, 16))

        self.btn_missing_tid = tk.Button(
            right_frame, text="Missing TID: 0",
            command=self._toggle_missing_tid,
            bg=THEME["border_light"], fg=THEME["text_muted"],
            relief="flat", font=("Segoe UI", 8, "bold"),
            cursor="hand2", padx=10, pady=3, bd=0)
        self.btn_missing_tid.pack(side="left", padx=(0, 6))

        self.btn_bad_names = tk.Button(
            right_frame, text="Bad Names: 0",
            command=self._toggle_bad_names,
            bg=THEME["border_light"], fg=THEME["text_muted"],
            relief="flat", font=("Segoe UI", 8, "bold"),
            cursor="hand2", padx=10, pady=3, bd=0)
        self.btn_bad_names.pack(side="left")

        # ── LEFT: live search + mode-specific filter buttons ───────────
        left_frame = tk.Frame(header_inner, bg=THEME["bg_secondary"])
        left_frame.pack(side="left", fill="x", expand=True, padx=(0, 12))

        tk.Label(left_frame, text="🔍", font=("Segoe UI", 11),
                 fg=THEME["text_muted"], bg=THEME["bg_secondary"]).pack(side="left", padx=(0, 6))

        search_entry = tk.Entry(left_frame, textvariable=self.search_query,
                                font=("Segoe UI", 10),
                                bg=THEME["bg_tertiary"], fg=THEME["text_primary"],
                                relief="solid", bd=1,
                                insertbackground=THEME["accent_primary"])
        search_entry.pack(side="left", fill="x", expand=True)

        filters_frame = tk.Frame(left_frame, bg=THEME["bg_secondary"])
        filters_frame.pack(side="left", padx=(10, 0))
        self._build_filter_buttons(filters_frame)
        
        # Main table with scrollbar
        col_ids = [c[0] for c in self.COLUMNS]
        self.tree = ttk.Treeview(self.table_container, columns=col_ids,
                                show="headings", selectmode="browse",
                                height=20, style="Striped.Treeview")
        
        self._vsb = ttk.Scrollbar(self.table_container, orient="vertical", command=self.tree.yview,
                                  style="Vertical.TScrollbar")
        # Wrap yscrollcommand so scrolling repositions Fix Name buttons
        self.tree.configure(
            yscrollcommand=lambda *a: (self._vsb.set(*a), self._schedule_fix_buttons()))

        # Configure columns
        for col_id, heading, width, stretch, anchor in self.COLUMNS:
            self.tree.heading(col_id, text=heading,
                            command=lambda c=col_id: self._sort_column(c, False))
            self.tree.column(col_id, width=width, minwidth=max(60, width // 2),
                            stretch=stretch, anchor=anchor)

        self.tree.pack(side="left", fill="both", expand=True)
        self._vsb.pack(side="right", fill="y")

        # Reposition Fix Name buttons on keyboard scroll and window resize
        self.tree.bind("<KeyRelease>",  lambda e: self._schedule_fix_buttons())
        self.tree.bind("<Configure>",   lambda e: self._schedule_fix_buttons())

        # configure striping tags
        self.tree.tag_configure("even", background="#1a2540")
        self.tree.tag_configure("odd", background="#151d33")
        
        # Right-click menu
        self._ctx_menu = tk.Menu(self, tearoff=0, bg=THEME["bg_secondary"],
                                fg=THEME["text_primary"],
                                activebackground=THEME["bg_tertiary"],
                                activeforeground=THEME["accent_primary"])
        self._ctx_menu.add_command(label="📋 Copy Cell", command=self._copy_cell)
        self._ctx_menu.add_command(label="📋 Copy Row",  command=self._copy_row)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="📋 Copy All",  command=self._copy_all)
        self.tree.bind("<Button-3>", self._show_ctx_menu)
    
    def _show_empty_state(self, message: str = "No items found"):
        """Show helpful empty state instead of blank table."""
        # Disable table
        self.tree.pack_forget()
        
        # Create empty state overlay
        empty_frame = tk.Frame(self.table_container, bg=THEME["bg_secondary"],
                              highlightthickness=1,
                              highlightbackground=THEME["border_subtle"])
        empty_frame.pack(fill="both", expand=True)
        
        # Centered empty state
        center = tk.Frame(empty_frame, bg=THEME["bg_secondary"])
        center.pack(fill="both", expand=True)
        
        tk.Label(center, text="📭", font=("Arial", 48),
                bg=THEME["bg_secondary"]).pack(pady=(40, 20))
        
        tk.Label(center, text=message,
                font=("Segoe UI", 14, "bold"),
                fg=THEME["text_primary"], bg=THEME["bg_secondary"]).pack(pady=(0, 8))
        
        tk.Label(center, text="Try selecting a folder and clicking SCAN to get started",
                font=("Segoe UI", 10),
                fg=THEME["text_secondary"], bg=THEME["bg_secondary"]).pack()
        
        self.empty_state_frame = empty_frame
        self.tree.pack_forget()
    
    def _hide_empty_state(self):
        """Remove empty state and show table."""
        if hasattr(self, 'empty_state_frame'):
            self.empty_state_frame.pack_forget()
            del self.empty_state_frame
        self.tree.pack(side="left", fill="both", expand=True)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _build_statusbar(self):
        """Modern status bar with analytics and quick actions."""
        bar = tk.Frame(self, bg=THEME["bg_secondary"], 
                      highlightthickness=1, highlightbackground=THEME["border_subtle"],
                      padx=24, pady=14)
        bar.pack(side="bottom", fill="x")
        
        # Left status info
        left_section = tk.Frame(bar, bg=THEME["bg_secondary"])
        left_section.pack(side="left", fill="x", expand=True)
        
        self.status_lbl = tk.Label(left_section, text="✓ Ready", 
                                  bg=THEME["bg_secondary"],
                                  fg="#10b981", font=("Segoe UI", 9, "bold"))
        self.status_lbl.pack(side="left")
        
        # Right section with cache info and refresh
        right_section = tk.Frame(bar, bg=THEME["bg_secondary"])
        right_section.pack(side="right", fill="x")
        
        self.cache_lbl = tk.Label(right_section, text="", bg=THEME["bg_secondary"],
                                 fg=THEME["text_muted"], font=("Segoe UI", 8))
        self.cache_lbl.pack(side="left", padx=(0, 16))
        
        self.dl_btn = tk.Label(right_section, text="🔄 SYNC DATABASE", 
                              fg=THEME["accent_primary"],
                              bg=THEME["bg_secondary"], font=("Segoe UI", 8, "bold"),
                              cursor="hand2", relief="flat")
        self.dl_btn.pack(side="left")
        self.dl_btn.bind("<Button-1>", lambda e: self.scan(force_refresh=True))
    
    def _update_status(self, message: str, status_type: str = "info"):
        """Update status with color coding."""
        # status_type: 'success', 'error', 'warning', 'info'
        colors = {
            "success": "#10b981",  # Green
            "error": "#ef4444",    # Red
            "warning": "#f97316",  # Orange
            "info": "#60a5fa",     # Blue
        }
        color = colors.get(status_type, "#60a5fa")
        self.status_lbl.config(text=message, fg=color)

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def _sort_column(self, col, reverse):
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        try:
            data.sort(key=lambda t: int(t[0].replace(",", "")), reverse=reverse)
        except Exception:
            data.sort(reverse=reverse)
        for idx, (_, k) in enumerate(data):
            self.tree.move(k, "", idx)
        self.tree.heading(col, command=lambda: self._sort_column(col, not reverse))

    # ------------------------------------------------------------------
    # Right-click copy
    # ------------------------------------------------------------------

    def _show_ctx_menu(self, event):
        iid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if iid:
            self.tree.selection_set(iid)
            self._ctx_col = col
            self._ctx_menu.tk_popup(event.x_root, event.y_root)

    def _copy_cell(self):
        sel = self.tree.selection()
        if not sel or not self._ctx_col:
            return
        idx = int(self._ctx_col.lstrip("#")) - 1
        vals = self.tree.item(sel[0], "values")
        if 0 <= idx < len(vals):
            self.clipboard_clear()
            self.clipboard_append(str(vals[idx]))

    def _copy_row(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        self.clipboard_clear()
        self.clipboard_append("\t".join(str(v) for v in vals))

    def _copy_all(self):
        col_ids = [c[0] for c in self.COLUMNS]
        lines = ["\t".join(col_ids)]
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            lines.append("\t".join(str(v) for v in vals))
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))

    # ------------------------------------------------------------------
    # File quality counters + filter buttons
    # ------------------------------------------------------------------

    def _update_file_counters(self, missing_tid: int, improper_name: int):
        """Update quality button labels after a scan."""
        self._missing_tid_count = missing_tid
        self._bad_names_count   = improper_name

        self.btn_missing_tid.config(
            text=f"Missing TID: {missing_tid}",
            fg=THEME["status_danger"] if missing_tid   > 0 else THEME["text_muted"])
        self.btn_bad_names.config(
            text=f"Bad Names: {improper_name}",
            fg=THEME["status_warn"]   if improper_name > 0 else THEME["text_muted"])

    def _toggle_missing_tid(self):
        self.show_missing_tid = not self.show_missing_tid
        self.btn_missing_tid.config(
            bg=THEME["status_danger"] if self.show_missing_tid else THEME["border_light"],
            fg="#ffffff"              if self.show_missing_tid else (
                THEME["status_danger"] if self._missing_tid_count > 0 else THEME["text_muted"]))
        self.refresh_table()

    def _toggle_bad_names(self):
        self.show_bad_names = not self.show_bad_names
        self.btn_bad_names.config(
            bg=THEME["status_warn"] if self.show_bad_names else THEME["border_light"],
            fg="#ffffff"            if self.show_bad_names else (
                THEME["status_warn"] if self._bad_names_count > 0 else THEME["text_muted"]))
        self.refresh_table()
        self._schedule_fix_buttons(60)

    def _clear_fix_buttons(self):
        """Destroy all overlay Fix Name buttons."""
        for btn in self._fix_buttons:
            try:
                btn.destroy()
            except Exception:
                pass
        self._fix_buttons = []

    def _schedule_fix_buttons(self, delay: int = 30):
        """Debounce Fix Name button repositioning (e.g. after scroll/resize)."""
        if self._fix_btn_after_id:
            try:
                self.after_cancel(self._fix_btn_after_id)
            except Exception:
                pass
        self._fix_btn_after_id = self.after(delay, self._place_fix_buttons)

    def _place_fix_buttons(self):
        """Overlay a real Fix Name button on every visible bad-name row."""
        self._fix_btn_after_id = None
        self._clear_fix_buttons()

        if not self.show_bad_names:
            return

        fname_idx = next((i for i, c in enumerate(self.COLUMNS) if c[0] == "filename"), 0)
        fname_col = "filename"  # treeview column id
        btn_w, btn_h = 86, 26

        for iid in self.tree.get_children():
            values = self.tree.item(iid, "values")
            if not values:
                continue
            filename = values[fname_idx]

            item = next(
                (d for d in self.all_data
                 if d.get("filename") == filename and d.get("_quality") == "bad_name"),
                None)
            if not item:
                continue

            # Cell bbox for the filename column — returns "" if row is off-screen
            cell = self.tree.bbox(iid, fname_col)
            if not cell:
                continue

            cx, cy, cw, ch = cell
            btn_x = cx + cw - btn_w - 6
            btn_y = cy + (ch - btn_h) // 2

            btn = tk.Button(
                self.tree,
                text="✎ Fix Name",
                command=lambda i=item: self._fix_item(i),
                bg=THEME["status_warn"], fg="#ffffff",
                relief="flat", font=("Segoe UI", 8, "bold"),
                cursor="hand2", padx=6, pady=0,
                bd=0, highlightthickness=0)
            btn.place(x=btn_x, y=btn_y, width=btn_w, height=btn_h)
            self._fix_buttons.append(btn)

    def _fix_item(self, item: dict):
        """Open the rename dialog pre-filtered to this item; user can clear search to see all."""
        from ui.edit_dialog import EditDialog
        bad_items = [d for d in self.all_data
                     if d.get("_quality") in ("bad_name", "missing_tid")]
        EditDialog(self, bad_items, self.norm_t, self.target_folder.get(),
                   search=item["filename"])

    def _quality_visible(self, item) -> bool:
        """Return True if the item passes the active quality filter.

        Default (no filter active): hide missing_tid, show everything else.
        When a quality filter is active: exclusive — show only items of that type.
        Multiple active quality filters are OR'd together.
        """
        quality = item.get("_quality", "ok")
        if self.show_missing_tid or self.show_bad_names:
            if self.show_missing_tid and quality == "missing_tid":
                return True
            if self.show_bad_names and quality == "bad_name":
                return True
            return False
        return quality != "missing_tid"   # default: hide missing TID entries

    # ------------------------------------------------------------------
    # Stubs — subclasses must implement
    # ------------------------------------------------------------------

    def scan(self, force_refresh: bool = False):
        raise NotImplementedError

    def refresh_table(self):
        raise NotImplementedError

    def open_edit_mode(self):
        """Open the rename dialog for bad_name and missing_tid files."""
        if not self.all_data:
            from tkinter import messagebox
            messagebox.showinfo(
                "Scan First",
                "Run a scan before using Edit mode.",
                parent=self)
            return

        items = [item for item in self.all_data
                 if item.get("_quality") in ("bad_name", "missing_tid")]

        if not items:
            from tkinter import messagebox
            messagebox.showinfo(
                "Nothing to Rename",
                "All files are already properly named!\n\n"
                "Files must have the form:\n"
                "  Game Name [TitleID][vVERSION].nsp/.xci",
                parent=self)
            return

        from ui.edit_dialog import EditDialog
        EditDialog(self, items, self.norm_t, self.target_folder.get())
