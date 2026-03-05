"""
splash.py — Premium splash screen for NX-Librarian.

Animated loading screen with:
- Growing circle animation
- Modern color scheme
- Smooth progress tracking
- Sophisticated visual presentation
- Professional polish
"""

import os
import tkinter as tk
import threading
import math
import time
import sys
import ctypes
import ctypes.util

_HERE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

try:
    from PIL import Image, ImageTk
    PILLOW_OK = True
except ImportError:
    PILLOW_OK = False


class _LinuxShapeHelper:
    """
    Uses the X11 Shape extension (libXext) to clip the splash window to a
    circle, giving true OS-level transparency outside the circle on Linux.
    Falls back silently if the extension is unavailable.
    """
    available = False

    def __init__(self, root, W, H):
        self._root = root
        self._W    = W
        self._H    = H
        self._x11  = None
        self._xext = None
        self._dpy  = None
        self._wid  = None
        self._setup()

    def _setup(self):
        try:
            x11_path  = ctypes.util.find_library("X11")
            xext_path = ctypes.util.find_library("Xext")
            if not x11_path or not xext_path:
                return

            x11  = ctypes.CDLL(x11_path)
            xext = ctypes.CDLL(xext_path)

            x11.XOpenDisplay.restype  = ctypes.c_void_p
            x11.XCreatePixmap.restype = ctypes.c_ulong
            x11.XCreateGC.restype     = ctypes.c_void_p

            dpy = x11.XOpenDisplay(None)
            if not dpy:
                return

            self._root.update_idletasks()
            self._x11  = x11
            self._xext = xext
            self._dpy  = dpy
            self._wid  = self._root.winfo_id()
            self.available = True
        except Exception:
            pass

    def clip_circle(self, cx, cy, radius):
        """Clip the window to a circle of *radius* centred at (cx, cy)."""
        if not self.available:
            return
        try:
            x11, xext = self._x11, self._xext
            dpy, wid  = self._dpy,  self._wid
            W, H      = self._W,    self._H

            # 1-bit pixmap used as shape mask
            pm = x11.XCreatePixmap(dpy, wid, W, H, 1)
            gc = x11.XCreateGC(dpy, pm, 0, None)

            # Fill entire pixmap with 0 → transparent / excluded
            x11.XSetForeground(dpy, gc, 0)
            x11.XFillRectangle(dpy, pm, gc, 0, 0, W, H)

            # Paint the circle with 1 → opaque / included
            r = max(1, radius)
            x11.XSetForeground(dpy, gc, 1)
            x11.XFillArc(dpy, pm, gc,
                         cx - r, cy - r, r * 2, r * 2,
                         0, 360 * 64)

            # Apply bounding shape: ShapeBounding=0, ShapeSet=0
            xext.XShapeCombineMask(dpy, wid, 0, 0, 0, pm, 0)

            x11.XFreeGC(dpy, gc)
            x11.XFreePixmap(dpy, pm)
            x11.XFlush(dpy)
        except Exception:
            self.available = False  # give up on error

    def cleanup(self):
        if self._dpy:
            try:
                self._x11.XCloseDisplay(self._dpy)
            except Exception:
                pass
        self.available = False


class SplashScreen:
    """
    Premium animated splash screen.
    
    Usage:
        splash = SplashScreen(on_complete_callback)
        splash.start(load_function)   # load_function(progress_cb) blocks until done
    """

    W, H        = 800, 600       # Splash window size
    MAX_RADIUS  = 350            # Circle grows to this pixel radius
    LOGO_W, LOGO_H = 480, 316   # Logo display size
    CX, CY      = 400, 270      # Circle/logo centre point
    PCT_Y_OFFSET = 50           # Pixels below logo bottom for percentage label

    # Modern color scheme
    BG_COLOR    = "#0a0a14"     # Deep space black
    CIRCLE_COLOR = "#0a0a14"    # Main circle (blends with BG)
    ACCENT_COLOR = "#60a5fa"    # Electric blue accent
    TEXT_PRIMARY = "#ffffff"
    TEXT_ACCENT = "#06d6d0"     # Fresh cyan

    def __init__(self, on_complete):
        self._on_complete     = on_complete
        self._progress        = 0.0   # target  (set by loader thread)
        self._display_progress = 0.0  # smoothed (advanced each frame)
        self._logo_img        = None
        self._start_time      = time.time()

        _is_mac   = sys.platform == "darwin"
        _is_win   = sys.platform == "win32"
        _is_linux = sys.platform.startswith("linux")

        if _is_mac:
            _bg_key = "systemTransparent"
        elif _is_win:
            _bg_key = "#000000"   # used as transparent color key on Windows
        else:
            _bg_key = "#ffffff"   # Linux: white background

        self.root = tk.Tk()
        self.root.overrideredirect(True)   # Borderless
        self.root.attributes("-topmost", True)
        if _is_mac:
            self.root.attributes("-transparent", True)
        elif _is_win:
            self.root.attributes("-transparentcolor", "#000000")
        self.root.configure(bg=_bg_key)

        # Centre the window on screen
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = (sw - self.W) // 2
        y  = (sh - self.H) // 2
        self.root.geometry(f"{self.W}x{self.H}+{x}+{y}")

        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H,
                                bg=_bg_key, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Draw initial state
        _circle_fill = "#e0e0e0" if _is_linux else "#ffffff"
        self._circle_id  = self.canvas.create_oval(0, 0, 0, 0,
                                                   fill=_circle_fill,
                                                   outline="")
        self._logo_id    = None
        self._pct_shadow = None
        self._pct_text   = None

        self._load_logo()
        self._draw_logo()
        self._draw_pct()

        # Fix z-order once: circle at bottom, logo above, pct text on top
        self.canvas.tag_lower(self._circle_id)
        if self._logo_id:
            self.canvas.tag_raise(self._logo_id)
        self.canvas.tag_raise(self._pct_shadow)
        self.canvas.tag_raise(self._pct_text)

        self._shaper = None

        # Kick off animation loop
        self._animate()

    # ------------------------------------------------------------------
    # Logo
    # ------------------------------------------------------------------

    def _load_logo(self):
        if not PILLOW_OK:
            return
        try:
            img = Image.open(os.path.join(_HERE, "logo.png")).convert("RGBA")
            # Preserve aspect ratio
            img.thumbnail((self.LOGO_W, self.LOGO_H), Image.Resampling.LANCZOS)
            
            # Place on a fully-transparent RGBA canvas so the alpha channel
            # is preserved when rendered on the tkinter canvas.
            bg = Image.new("RGBA", (self.LOGO_W, self.LOGO_H), (0, 0, 0, 0))
            offset = ((self.LOGO_W - img.width) // 2, (self.LOGO_H - img.height) // 2)
            bg.paste(img, offset, mask=img.split()[3])

            self._logo_img = ImageTk.PhotoImage(bg)
        except Exception:
            self._logo_img = None

    def _draw_logo(self):
        if self._logo_img:
            if self._logo_id:
                self.canvas.delete(self._logo_id)
            self._logo_id = self.canvas.create_image(
                self.CX, self.CY, image=self._logo_img, anchor="center"
            )
        else:
            # Fallback text logo
            self._logo_id = self.canvas.create_text(
                self.CX, self.CY,
                text="NX-LIBRARIAN",
                font=("Segoe UI", 36, "bold"),
                fill=self.TEXT_PRIMARY,
                anchor="center",
            )

    # ------------------------------------------------------------------
    # Percentage text with modern styling
    # ------------------------------------------------------------------

    def _pct_y(self):
        """Y coordinate for the percentage label."""
        return self.CY + self.LOGO_H // 2 + self.PCT_Y_OFFSET

    def _draw_pct(self):
        text = f"{int(self._display_progress)}%"
        if self._pct_shadow is None:
            # Create items once
            y = self._pct_y()
            self._pct_shadow = self.canvas.create_text(
                self.CX + 2, y + 2,
                text=text,
                font=("Segoe UI", 28, "bold"),
                fill="#0a0a14",
                anchor="center",
            )
            self._pct_text = self.canvas.create_text(
                self.CX, y,
                text=text,
                font=("Segoe UI", 28, "bold"),
                fill=self.TEXT_ACCENT,
                anchor="center",
            )
        else:
            # Just update the text in place — no delete/recreate
            self.canvas.itemconfig(self._pct_shadow, text=text)
            self.canvas.itemconfig(self._pct_text, text=text)

    # ------------------------------------------------------------------
    # Animation loop
    # ------------------------------------------------------------------

    def _animate(self):
        """Smooth animation of the growing circle."""
        # Lerp display progress toward the target each frame (~8% per frame at 60fps)
        target = max(0.0, min(100.0, self._progress))
        self._display_progress += (target - self._display_progress) * 0.08
        if target - self._display_progress < 0.05:
            self._display_progress = target  # snap when close enough

        pct = self._display_progress
        # Ease-out: sqrt provides fast start, slowing growth
        ratio = math.sqrt(pct / 100.0)
        radius = int(ratio * self.MAX_RADIUS)

        x0 = self.CX - radius
        y0 = self.CY - radius
        x1 = self.CX + radius
        y1 = self.CY + radius
        self.canvas.coords(self._circle_id, x0, y0, x1, y1)

        self._draw_pct()

        if self._display_progress < 100.0:
            self.root.after(16, self._animate)
        else:
            # Enforce minimum 3 second display, then blast out
            elapsed = time.time() - self._start_time
            remaining = max(0, 3.0 - elapsed)
            delay_ms = int(remaining * 1000) + 300
            self.root.after(delay_ms, self._start_outro)

    # ------------------------------------------------------------------
    # Outro: circle explodes, everything fades to transparent
    # ------------------------------------------------------------------

    _WINDUP_FRAMES = 10  # ~160 ms — snappy pull-back to 70% radius
    _OUTRO_FRAMES  = 35  # ~560 ms at 16 ms/frame

    def _start_outro(self):
        """Kick off the outro — hide pct text, spring back, then explode."""
        self.canvas.itemconfig(self._pct_shadow, state="hidden")
        self.canvas.itemconfig(self._pct_text,   state="hidden")
        self._windup_frame = 0
        self._windup()

    def _windup(self):
        """Contract circle to 70% size — the 'boing' ramp-up before explosion."""
        t    = self._windup_frame / self._WINDUP_FRAMES   # 0.0 → 1.0
        ease = t * t   # ease-in: lingers briefly then snaps back fast

        r_start = self.MAX_RADIUS                             # 100% radius
        r_end   = int(math.sqrt(0.10) * self.MAX_RADIUS)     # 10% radius
        radius  = int(r_start + (r_end - r_start) * ease)

        self.canvas.coords(self._circle_id,
                           self.CX - radius, self.CY - radius,
                           self.CX + radius, self.CY + radius)

        self._windup_frame += 1
        if t < 1.0:
            self.root.after(16, self._windup)
        else:
            self._outro_frame = 0
            self._outro()

    def _outro(self):
        """One frame of the outro: blast circle outward + fade once past 100%."""
        t = self._outro_frame / self._OUTRO_FRAMES   # 0.0 → 1.0

        # Ease-in (t²) for an accelerating blast.
        # Start from the windup's resting point (70% radius) → 5× MAX_RADIUS.
        ease    = t * t
        r_start = int(math.sqrt(0.10) * self.MAX_RADIUS)   # ~111 px
        r_end   = self.MAX_RADIUS * 5                       # 1750 px
        radius  = int(r_start + (r_end - r_start) * ease)

        self.canvas.coords(self._circle_id,
                           self.CX - radius, self.CY - radius,
                           self.CX + radius, self.CY + radius)

        # Fade only after the circle blasts back through the 100% size
        if radius > self.MAX_RADIUS:
            fade_range = r_end - self.MAX_RADIUS
            fade_t     = (radius - self.MAX_RADIUS) / fade_range
            alpha      = max(0.0, 1.0 - fade_t)
            try:
                self.root.attributes("-alpha", alpha)
            except Exception:
                pass

        self._outro_frame += 1
        if t < 1.0:
            self.root.after(16, self._outro)
        else:
            self.root.after(50, self._finish)

    def _finish(self):
        """Exit the splash mainloop; cleanup and on_complete run after mainloop() returns."""
        if self._shaper:
            self._shaper.cleanup()
        self.root.quit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_progress(self, pct: float):
        """Thread-safe progress update (0.0–100.0)."""
        self._progress = max(0.0, min(100.0, float(pct)))

    def start(self, load_fn):
        """
        Run load_fn(progress_cb) in a background thread.
        
        load_fn must accept one argument: a callable(float) for progress.
        """
        def _worker():
            try:
                load_fn(self.set_progress)
            except Exception:
                self.set_progress(100)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        self.root.mainloop()
        self.root.destroy()
        self._on_complete()
