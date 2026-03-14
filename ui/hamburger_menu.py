"""
ui/hamburger_menu.py — Custom-styled hamburger dropdown menu.

Replaces tk.Menu with a fully themed Toplevel-based dropdown that
matches the app's neon dark aesthetic instead of delegating to the
Win32 native menu renderer.

Dismiss strategy (Windows):
  - 50 ms poll using GetAsyncKeyState + GetCursorPos (pure main-thread ctypes,
    no hooks, no GIL issues).  Any mouse button pressed while cursor is outside
    the menu → dismiss.
  - focus_displayof() None check in same poll → catches keyboard alt-tab.
  - parent <Unmap> → catches minimize.

Dismiss strategy (non-Windows fallback):
  - grab_set() + <Button-1> for in-app clicks.
  - Same poll / <Unmap>.

Item format (list passed to HamburgerMenu):
  None                               → horizontal separator
  (icon, label, accel, cmd, checked) → menu item
    checked: True/False = checkable (shows dot indicator)
             None       = plain item
"""

import sys
import tkinter as tk
from constants import UI_FONT, FONT_BOOST, HAND_CURSOR

_F      = FONT_BOOST
_IS_WIN = sys.platform == "win32"

if _IS_WIN:
    import ctypes
    import ctypes.wintypes

    _user32 = ctypes.windll.user32

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    _user32.GetCursorPos.argtypes  = [ctypes.POINTER(_POINT)]
    _user32.GetCursorPos.restype   = ctypes.wintypes.BOOL
    _user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    _user32.GetAsyncKeyState.restype  = ctypes.c_short

    _VK_LBUTTON = 0x01
    _VK_RBUTTON = 0x02
    _VK_MBUTTON = 0x04

# Colors — matched to THEME in base_screen.py
_BG      = "#151d33"
_BG_HOV  = "#1f2847"
_FG      = "#e2e8f0"
_FG_HOV  = "#93c5fd"
_FG_DIM  = "#4b5563"
_FG_DIM2 = "#6b7280"
_FG_CHK  = "#60a5fa"
_BORDER  = "#2a3f5f"
_SEP     = "#1e2d4a"
_ACCENT  = "#60a5fa"


class HamburgerMenu(tk.Toplevel):
    """
    Fully custom dropdown menu that matches the app theme.

    anchor_right_x: screen X of the button's right edge — menu right-aligns here.
    y:              screen Y just below the button.
    """

    def __init__(self, parent, items, anchor_right_x, y):
        super().__init__(parent)
        self._parent = parent

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=_BORDER)

        # Border wrap
        wrap = tk.Frame(self, bg=_BORDER)
        wrap.pack(fill="both", expand=True, padx=1, pady=1)

        # Accent stripe
        tk.Frame(wrap, height=2, bg=_ACCENT).pack(fill="x")

        # Content
        content = tk.Frame(wrap, bg=_BG, pady=4)
        content.pack(fill="both", expand=True)

        for item in items:
            if item is None:
                tk.Frame(content, height=1, bg=_SEP).pack(
                    fill="x", padx=10, pady=2)
            else:
                self._build_row(content, *item)

        # Position: right-align under anchor_right_x, clamp to screen
        self.update_idletasks()
        W  = self.winfo_reqwidth()
        H  = self.winfo_reqheight()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = max(4, anchor_right_x - W)
        if y + H > sh - 8:
            y = sh - H - 8
        self.geometry(f"+{x}+{y}")

        # Dismiss on minimize
        self._app_root = parent.winfo_toplevel()
        self._unmap_id = self._app_root.bind(
            "<Unmap>", lambda e: self._dismiss(), "+")
        self.bind("<Escape>", lambda e: self._dismiss())

        if not _IS_WIN:
            self.grab_set()
            self.bind("<Button-1>", self._on_toplevel_click)

        # Don't watch for outside clicks until the opening click is released
        self._btn_released = False
        self.after(50, self._poll)

    # ── Poll (runs in main thread — no GIL concerns) ───────────────────────────

    def _poll(self):
        try:
            if not self.winfo_exists():
                return

            if _IS_WIN:
                pressed = bool(
                    _user32.GetAsyncKeyState(_VK_LBUTTON) & 0x8000 or
                    _user32.GetAsyncKeyState(_VK_RBUTTON) & 0x8000 or
                    _user32.GetAsyncKeyState(_VK_MBUTTON) & 0x8000
                )
                if not self._btn_released:
                    # Wait for the opening click to finish before watching
                    if not pressed:
                        self._btn_released = True
                elif pressed:
                    pt = _POINT()
                    _user32.GetCursorPos(ctypes.byref(pt))
                    wx = self.winfo_rootx()
                    wy = self.winfo_rooty()
                    ww = self.winfo_width()
                    wh = self.winfo_height()
                    if not (wx <= pt.x <= wx + ww and wy <= pt.y <= wy + wh):
                        self._dismiss()
                        return

            # Alt-tab / app lost focus
            if self._app_root.focus_displayof() is None:
                self._dismiss()
                return

        except Exception:
            pass

        self.after(50, self._poll)

    # ── Non-Windows fallback ───────────────────────────────────────────────────

    def _on_toplevel_click(self, event):
        if event.widget is self:
            self._dismiss()

    # ── Row construction ───────────────────────────────────────────────────────

    def _build_row(self, parent, icon, label, accel, cmd, checked):
        row = tk.Frame(parent, bg=_BG, cursor=HAND_CURSOR)
        row.pack(fill="x", padx=2)

        dot_norm = _FG_CHK if checked else _BG
        dot_hov  = _FG_CHK if checked else _BG_HOV
        dot = tk.Label(row, text="●", fg=dot_norm, bg=_BG,
                       font=(UI_FONT, 7 + _F), width=1, anchor="center")
        dot.pack(side="left", padx=(8, 0), pady=2)

        ico = tk.Label(row, text=icon, bg=_BG, fg=_FG,
                       font=(UI_FONT, 11 + _F), width=2, anchor="center")
        ico.pack(side="left", padx=(4, 0), pady=2)

        lbl = tk.Label(row, text=f"  {label}", bg=_BG, fg=_FG,
                       font=(UI_FONT, 10 + _F), anchor="w")
        lbl.pack(side="left", padx=(0, 20), pady=5, fill="x", expand=True)

        color_map = [
            (dot, dot_norm, dot_hov),
            (ico, _FG,      _FG_HOV),
            (lbl, _FG,      _FG_HOV),
        ]
        if accel:
            acc = tk.Label(row, text=accel, bg=_BG, fg=_FG_DIM,
                           font=(UI_FONT, 9 + _F), anchor="e")
            acc.pack(side="right", padx=(0, 14), pady=5)
            color_map.append((acc, _FG_DIM, _FG_DIM2))

        all_wids = [row] + [w for w, _, _ in color_map]
        for w in all_wids:
            w.bind("<Enter>",    lambda e, r=row, cm=color_map:
                                     self._on_enter(r, cm))
            w.bind("<Leave>",    lambda e, r=row, cm=color_map:
                                     self._on_leave(r, cm, e))
            w.bind("<Button-1>", lambda e, c=cmd: self._invoke(c))

    # ── Hover ──────────────────────────────────────────────────────────────────

    def _on_enter(self, row, color_map):
        row.config(bg=_BG_HOV)
        for w, _, hov_fg in color_map:
            w.config(bg=_BG_HOV, fg=hov_fg)

    def _on_leave(self, row, color_map, event):
        new_w = event.widget.winfo_containing(event.x_root, event.y_root)
        if new_w and (new_w is row or str(new_w).startswith(str(row) + ".")):
            return
        row.config(bg=_BG)
        for w, norm_fg, _ in color_map:
            w.config(bg=_BG, fg=norm_fg)

    # ── Invoke / dismiss ───────────────────────────────────────────────────────

    def _invoke(self, cmd):
        parent = self._parent
        self._dismiss()
        if cmd:
            parent.after(20, cmd)

    def _dismiss(self):
        try:
            self._app_root.unbind("<Unmap>", self._unmap_id)
        except Exception:
            pass
        if not _IS_WIN:
            try:
                self.grab_release()
            except Exception:
                pass
        try:
            self.destroy()
        except Exception:
            pass
