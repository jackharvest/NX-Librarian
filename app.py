"""
app.py — NX-Librarian main application window.

Manages the three mode screens (Base Games, Updates, DLC) and the
mode-select landing screen. Handles frame routing and logo loading.

Professional features:
- Menu bar with standard file/view/help menus
- Keyboard shortcuts throughout
- Professional window setup
"""

import os
import tkinter as tk

from constants import UI_FONT, FONT_BOOST, HAND_CURSOR
_HERE = os.path.dirname(os.path.abspath(__file__))
_F = FONT_BOOST

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
    def __init__(self, root, norm_v=None, norm_t=None, norm_c=None, prescan_data=None):
        self.root          = root
        self.norm_v        = norm_v or {}
        self.norm_t        = norm_t or {}
        self.norm_c        = norm_c or {}
        self._prescan_data = prescan_data or {}

        self.root.title("NX-Librarian — Nintendo Switch Archive Manager & Renamer")
        self.root.geometry("1100x880")
        self.root.configure(bg="#0a0a14")
        self.root.minsize(800, 600)

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
        self._nav_history   = []   # stack of (restore_callable) for back navigation

        # Keyboard shortcuts
        self._setup_shortcuts()

        self._show_mode_select()

        # Load persistent art-mode setting
        from ui import icon_cache as _ic
        _ic.load_enabled()

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
            banner_img_path = Image.open(os.path.join(_HERE, "logo_fullbar_thinner.png")).convert("RGBA")
            banner_img = ImageTk.PhotoImage(banner_img_path)
            banner_label = tk.Label(self._banner_frame, image=banner_img, bg="#111e2f")
            banner_label.pack(fill="x", expand=True)
            self._banner_img_ref = banner_img
        except Exception:
            pass

        # Hamburger button — overlaid on top-right corner of the banner
        self._hamburger_btn = tk.Label(
            self._banner_frame, text="☰",
            font=(UI_FONT, 16 + _F), fg="#9ca3af", bg="#111e2f",
            cursor=HAND_CURSOR, padx=12, pady=8)
        self._hamburger_btn.bind("<Button-1>", lambda e: self._show_hamburger_menu())
        self._hamburger_btn.bind("<Enter>", lambda e: self._hamburger_btn.config(bg="#1f2847", fg="#ffffff"))
        self._hamburger_btn.bind("<Leave>", lambda e: self._hamburger_btn.config(bg="#111e2f", fg="#9ca3af"))
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
        menu.add_command(label="  ⚙   Database Mirror",
                         command=self._show_mirror_dialog)
        from ui import icon_cache as _ic
        art_label = "  🖼   Art Mode  ✓" if _ic.is_enabled() else "  🖼   Art Mode"
        menu.add_command(label=art_label, command=self._toggle_art_mode)
        menu.add_command(label="  ℹ   About",
                         command=self._show_about)
        menu.add_command(label="  ★   Credits",
                         command=self._show_credits)
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
            "Nintendo Switch Archive Manager & Renamer\n\n"
            "Manage, organize, and verify your game collection.\n"
            "Support for base games, updates, and DLC.\n\n"
            "Art Mode: toggle in-row banner art sourced from\n"
            "the Nintendo eShop CDN via blawar/titledb.\n\n"
            "© 2026 jackharvest / NX-Librarian Contributors")

    def _show_credits(self):
        from ui.credits import show_credits
        show_credits(self.root)

    def _show_mirror_dialog(self):
        from ui.mirror_dialog import show_mirror_dialog
        show_mirror_dialog(self.root)

    def _toggle_art_mode(self):
        from ui import icon_cache as _ic
        _ic.set_enabled(not _ic.is_enabled())
        if hasattr(self._current_frame, "_on_art_mode_changed"):
            self._current_frame._on_art_mode_changed()

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
            try:
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
            img = Image.open(os.path.join(_HERE, "logo_tophalf.png")).convert("RGBA")
            # Preserve aspect ratio - fit within the box without stretching
            img.thumbnail((w, h), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Frame routing
    # ------------------------------------------------------------------

    def _go_back(self):
        """Navigate to the previous screen, or mode select if no history."""
        if self._nav_history:
            self._nav_history.pop()()
        else:
            self._show_mode_select()

    def _swap(self, frame):
        if self._current_frame:
            self._current_frame.pack_forget()
        frame.pack(fill="both", expand=True, in_=self._content_container)
        self._current_frame = frame

    def _show_mode_select(self):
        self._nav_history.clear()   # mode select is always the root
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
        screen = self._mode_screens[mode]
        screen.search_query.set("")  # Clear filter when entering from mode select
        self._swap(screen)
        self._current_mode = mode
        self.root.configure(bg="#ffffff")

        if hasattr(screen, "_prescan_ready"):
            # Data was loaded during splash — just render it
            del screen._prescan_ready
            self.root.after(50, screen.refresh_table)
        elif (self._mode_select_screen.pre_scan_enabled
              and screen.target_folder.get()
              and not screen.all_data):
            # Fallback: scan now (pre-scan was off or folder wasn't cached at launch)
            self.root.after(50, screen.scan)

    def _navigate_to(self, mode: str, tid: str):
        """Switch to mode screen and filter by the game's TID prefix."""
        # Capture current screen state so back can restore it
        prev_mode   = self._current_mode
        prev_filter = (self._mode_screens[prev_mode].search_query.get()
                       if prev_mode and prev_mode in self._mode_screens else "")

        def _restore():
            if prev_mode is None:
                self._show_mode_select()
            else:
                screen = self._mode_screens[prev_mode]
                screen.search_query.set(prev_filter)
                self._swap(screen)
                self._current_mode = prev_mode
                self.root.configure(bg="#ffffff")

        self._nav_history.append(_restore)
        self._on_mode_selected(mode)
        # First 13 chars of any Switch TID identify the game — shared by base, update, and all DLC
        self._mode_screens[mode].search_query.set(tid[:13])

    def _build_screen(self, mode: str):
        common = dict(
            parent=self._content_container,
            on_back=self._go_back,
            logo_img=self._logo_header,
            norm_v=self.norm_v,
            norm_t=self.norm_t,
            norm_c=self.norm_c,
            navigate_to=self._navigate_to,
        )
        if mode == "updates":
            screen = UpdatesScreen(**common)
        elif mode == "base":
            screen = BaseGamesScreen(**common)
        elif mode == "dlc":
            screen = DLCScreen(**common)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        # Inject pre-scanned data if available
        if mode in self._prescan_data:
            from db import cache_age_string
            all_data, missing, improper, unknown = self._prescan_data[mode]
            screen.all_data = all_data
            screen._update_file_counters(missing, improper, unknown)
            screen._update_status(f"✓ Pre-scanned {len(all_data)} items", "success")
            screen.cache_lbl.config(text=cache_age_string())
            screen._prescan_ready = True   # flag for _on_mode_selected

        return screen
