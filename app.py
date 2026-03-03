"""
app.py — NX-Librarian main application window.

Manages the three mode screens (Base Games, Updates, DLC) and the
mode-select landing screen. Handles frame routing and logo loading.

Professional features:
- Menu bar with standard file/view/help menus
- Keyboard shortcuts throughout
- Professional window setup
"""

import tkinter as tk

try:
    from PIL import Image, ImageTk
    PILLOW_OK = True
except ImportError:
    PILLOW_OK = False

from ui.mode_select import ModeSelectScreen
from ui.updates_screen import UpdatesScreen
from ui.base_games_screen import BaseGamesScreen
from ui.dlc_screen import DLCScreen

# Logo display size in the header bar of each mode screen
HEADER_LOGO_W = 400
HEADER_LOGO_H = 100


class NXLibrarianApp:
    def __init__(self, root, norm_v=None, norm_t=None, norm_c=None):
        self.root   = root
        self.norm_v = norm_v or {}
        self.norm_t = norm_t or {}
        self.norm_c = norm_c or {}

        self.root.title("NX-Librarian — Nintendo Switch Archive Manager & Renamer")
        self.root.geometry("1350x880")
        self.root.configure(bg="#0a0a14")
        self.root.minsize(900, 600)

        # Load logos
        self._logo_full   = self._load_logo(480, 316)   # mode select
        self._logo_header = self._load_logo(HEADER_LOGO_W, HEADER_LOGO_H)  # screen headers

        # Build persistent top banner
        self._build_banner()
        
        # Create content container for screen swapping
        self._content_container = tk.Frame(self.root, bg="#0a0a14")
        self._content_container.pack(fill="both", expand=True)

        # Active frame reference
        self._current_frame = None
        self._current_mode = None
        self._mode_screens  = {}

        # Keyboard shortcuts
        self._setup_shortcuts()

        self._show_mode_select()

        # Match title bar chrome to the OS dark/light mode setting
        self._apply_os_title_bar_theme()

    # ------------------------------------------------------------------
    # Banner
    # ------------------------------------------------------------------
    
    def _build_banner(self):
        """Build persistent top banner with logo and hamburger menu button."""
        self._banner_frame = tk.Frame(self.root, bg="#111e2f")
        self._banner_frame.pack(fill="x", side="top")

        try:
            banner_img_path = Image.open("logo_fullbar_thinner.png").convert("RGBA")
            banner_img = ImageTk.PhotoImage(banner_img_path)
            banner_label = tk.Label(self._banner_frame, image=banner_img, bg="#111e2f")
            banner_label.pack(fill="x", expand=True)
            self._banner_img_ref = banner_img
        except Exception:
            pass

        # Hamburger button — overlaid on top-right corner of the banner
        self._hamburger_btn = tk.Button(
            self._banner_frame, text="☰",
            font=("Segoe UI", 16), fg="#9ca3af", bg="#111e2f",
            relief="flat", bd=0, padx=12, pady=8,
            cursor="hand2",
            activebackground="#1f2847", activeforeground="#ffffff",
            command=self._show_hamburger_menu)
        self._hamburger_btn.place(relx=1.0, rely=0.0, anchor="ne")
        self._hamburger_btn.lift()

    # ------------------------------------------------------------------
    # Hamburger menu
    # ------------------------------------------------------------------

    def _show_hamburger_menu(self):
        """Pop up the app menu from the hamburger button."""
        menu = tk.Menu(self.root, tearoff=0,
                       bg="#151d33", fg="#ffffff",
                       activebackground="#60a5fa", activeforeground="#0a0a14",
                       font=("Segoe UI", 10), bd=0, relief="flat")

        menu.add_command(label="  ⌂   Mode Select",
                         command=self._show_mode_select, accelerator="ESC")
        menu.add_separator()
        menu.add_command(label="  ⛶   Fullscreen",
                         command=self._toggle_fullscreen, accelerator="F11")
        menu.add_separator()
        menu.add_command(label="  ⌨   Keyboard Shortcuts",
                         command=self._show_shortcuts)
        menu.add_command(label="  ℹ   About",
                         command=self._show_about)
        menu.add_separator()
        menu.add_command(label="  ✕   Exit",
                         command=self.root.quit, accelerator="Ctrl+Q")

        btn = self._hamburger_btn
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        state = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not state)

    def _show_about(self):
        """Show about dialog."""
        from tkinter import messagebox
        from constants import APP_VERSION
        messagebox.showinfo("About NX-Librarian",
            f"NX-Librarian v{APP_VERSION}\n\n"
            "Premium Nintendo Switch Archive Manager & Renamer\n\n"
            "Manage, organize, and renew your game collection.\n"
            "Support for base games, updates, and DLC.\n\n"
            "© 2026 • Enhanced with Premium Design")

    def _show_shortcuts(self):
        """Show keyboard shortcuts dialog."""
        from tkinter import messagebox
        shortcuts = (
            "KEYBOARD SHORTCUTS\n\n"
            "Ctrl+S  —  Scan library\n"
            "Ctrl+O  —  Browse folder\n"
            "Ctrl+F  —  Focus search\n"
            "F5      —  Refresh\n"
            "ESC     —  Back to mode select\n"
            "F11     —  Toggle fullscreen\n"
            "Ctrl+Q  —  Quit"
        )
        messagebox.showinfo("Keyboard Shortcuts", shortcuts)

    # ------------------------------------------------------------------
    # Keyboard Shortcuts
    # ------------------------------------------------------------------

    def _setup_shortcuts(self):
        """Wire keyboard shortcuts."""
        self.root.bind("<Control-q>", lambda e: self.root.quit())
        self.root.bind("<Control-s>", lambda e: self._trigger_scan())
        self.root.bind("<Control-o>", lambda e: self._trigger_browse())
        self.root.bind("<Control-f>", lambda e: self._trigger_search_focus())
        self.root.bind("<Escape>", lambda e: self._show_mode_select())
        self.root.bind("<F5>", lambda e: self._trigger_scan())
        self.root.bind("<F11>", lambda e: self._toggle_fullscreen())

    def _apply_os_title_bar_theme(self):
        """Match the Win32 title bar chrome to the OS dark/light mode (Windows only)."""
        try:
            import ctypes
            import winreg

            # 0 = dark mode, 1 = light mode
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            dark = (value == 0)

            # winfo_id() returns the inner Tk client HWND; the Win32 frame window
            # that owns the title bar is its parent.
            self.root.update()
            hwnd = self.root.winfo_id()
            parent = ctypes.windll.user32.GetParent(hwnd)
            frame_hwnd = parent if parent else hwnd

            mode = ctypes.c_int(1 if dark else 0)
            # Try attr 20 (Win11 / Win10 20H1+) then 19 (earlier Win10)
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    frame_hwnd, attr,
                    ctypes.byref(mode), ctypes.sizeof(mode))
        except Exception:
            pass   # Non-Windows or API unavailable — silently skip

    def _trigger_scan(self):
        """Trigger scan on current screen if available."""
        if hasattr(self._current_frame, 'scan'):
            self._current_frame.scan()

    def _trigger_browse(self):
        """Trigger browse on current screen if available."""
        if hasattr(self._current_frame, '_browse'):
            self._current_frame._browse()

    def _trigger_search_focus(self):
        """Focus search field on current screen if available."""
        if hasattr(self._current_frame, 'search_query'):
            # Try to find and focus the search entry widget
            try:
                # Find the entry widget with search_query variable
                for widget in self.root.winfo_descendants():
                    if isinstance(widget, tk.Entry) and hasattr(widget, 'var'):
                        if widget.var == self._current_frame.search_query:
                            widget.focus_set()
                            break
            except:
                pass

    # ------------------------------------------------------------------
    # Logo
    # ------------------------------------------------------------------

    def _load_logo(self, w, h):
        if not PILLOW_OK:
            return None
        try:
            img = Image.open("logo_tophalf.png").convert("RGBA")
            # Preserve aspect ratio - fit within the box without stretching
            img.thumbnail((w, h), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Frame routing
    # ------------------------------------------------------------------

    def _swap(self, frame):
        if self._current_frame:
            self._current_frame.pack_forget()
        frame.pack(fill="both", expand=True, in_=self._content_container)
        self._current_frame = frame

    def _show_mode_select(self):
        if not hasattr(self, "_mode_select_screen"):
            self._mode_select_screen = ModeSelectScreen(
                self._content_container,
                on_select=self._on_mode_selected,
                logo_img=self._logo_full,
            )
        self._swap(self._mode_select_screen)
        self._current_mode = None
        self.root.configure(bg="#0a0a14")

    def _on_mode_selected(self, mode: str):
        if mode not in self._mode_screens:
            self._mode_screens[mode] = self._build_screen(mode)
        self._swap(self._mode_screens[mode])
        self._current_mode = mode
        self.root.configure(bg="#ffffff")

    def _build_screen(self, mode: str):
        common = dict(
            parent=self._content_container,
            on_back=self._show_mode_select,
            logo_img=self._logo_header,
            norm_v=self.norm_v,
            norm_t=self.norm_t,
            norm_c=self.norm_c,
        )
        if mode == "updates":
            return UpdatesScreen(**common)
        if mode == "base":
            return BaseGamesScreen(**common)
        if mode == "dlc":
            return DLCScreen(**common)
        raise ValueError(f"Unknown mode: {mode}")
