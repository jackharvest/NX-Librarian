"""
ui/popup_utils.py — Shared theme helper for all custom Toplevel windows.

Call apply_window_theme(win) on any tk.Toplevel to get:
  • The app favicon instead of the default tkinter feather icon
  • A dark Win32 title-bar chrome (matches our always-dark UI)
"""

import os
import sys
import ctypes

# From source:  ui/popup_utils.py lives in ui/ → root is one level up
# From bundle:  sys._MEIPASS already points to the bundle root
_UI_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT   = getattr(sys, '_MEIPASS', os.path.dirname(_UI_DIR))
_ICO    = os.path.join(_ROOT, "icon.ico")


def apply_window_theme(win):
    """
    Apply the app favicon and a dark Win32 title bar to *win*.

    Safe to call on any platform — silently skips on non-Windows or when DWM
    is unavailable.  Must be called after the Toplevel has been created.
    """
    # ── Favicon ───────────────────────────────────────────────────────────
    if os.path.exists(_ICO):
        try:
            win.iconbitmap(_ICO)
        except Exception:
            pass

    # ── Dark title bar (Windows / DWM only) ──────────────────────────────
    try:
        # update_idletasks() ensures the native Win32 HWND has been created
        win.update_idletasks()
        hwnd = win.winfo_id()
        # winfo_id() returns the inner Tk client HWND; GetParent() gives the
        # outer frame window that actually owns the title bar chrome.
        parent_hwnd = ctypes.windll.user32.GetParent(hwnd)
        frame_hwnd  = parent_hwnd if parent_hwnd else hwnd

        dark = ctypes.c_int(1)   # 1 = dark chrome — our UI is always dark
        for attr in (20, 19):    # attr 20 = Win11/10 20H1+, 19 = earlier Win10
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                frame_hwnd, attr,
                ctypes.byref(dark), ctypes.sizeof(dark))
    except Exception:
        pass  # Non-Windows or DWM unavailable — skip silently
