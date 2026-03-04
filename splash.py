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

_HERE = os.path.dirname(os.path.abspath(__file__))

try:
    from PIL import Image, ImageTk
    PILLOW_OK = True
except ImportError:
    PILLOW_OK = False


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
        self._on_complete  = on_complete
        self._progress     = 0.0   # 0.0 – 100.0
        self._logo_img     = None
        self._start_time   = time.time()

        _is_mac   = sys.platform == "darwin"
        _is_win   = sys.platform == "win32"
        _bg_key   = "systemTransparent" if _is_mac else "#000000"

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
        self._circle_id  = self.canvas.create_oval(0, 0, 0, 0,
                                                   fill="#ffffff",
                                                   outline="")
        self._logo_id    = None
        self._pct_shadow = None
        self._pct_text   = None

        self._load_logo()
        self._draw_logo()
        self._draw_pct()

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
        y = self._pct_y()
        text = f"{int(self._progress)}%"

        # Remove old text items
        for item in (self._pct_shadow, self._pct_text):
            if item:
                self.canvas.delete(item)

        # Draw shadow with offset (#0a0a14 ≈ black but avoids the transparent key color)
        self._pct_shadow = self.canvas.create_text(
            self.CX + 2, y + 2,
            text=text,
            font=("Segoe UI", 28, "bold"),
            fill="#0a0a14",
            anchor="center",
        )
        
        # Main text in accent color
        self._pct_text = self.canvas.create_text(
            self.CX, y,
            text=text,
            font=("Segoe UI", 28, "bold"),
            fill=self.TEXT_ACCENT,
            anchor="center",
        )

        # Layer management
        if self._logo_id:
            self.canvas.tag_raise(self._logo_id)
        self.canvas.tag_raise(self._pct_shadow)
        self.canvas.tag_raise(self._pct_text)

    # ------------------------------------------------------------------
    # Animation loop
    # ------------------------------------------------------------------

    def _animate(self):
        """Smooth animation of the growing circle."""
        pct = max(0.0, min(100.0, self._progress))
        # Ease-out: sqrt provides fast start, slowing growth
        ratio = math.sqrt(pct / 100.0)
        radius = int(ratio * self.MAX_RADIUS)

        x0 = self.CX - radius
        y0 = self.CY - radius
        x1 = self.CX + radius
        y1 = self.CY + radius
        self.canvas.coords(self._circle_id, x0, y0, x1, y1)

        # Keep circle behind logo
        self.canvas.tag_lower(self._circle_id)
        if self._logo_id:
            self.canvas.tag_raise(self._logo_id)

        self._draw_pct()
        self.root.update_idletasks()

        if pct < 100.0:
            self.root.after(16, self._animate)
        else:
            # Enforce minimum 3 second display
            elapsed = time.time() - self._start_time
            remaining = max(0, 3.0 - elapsed)
            delay_ms = int(remaining * 1000) + 300
            self.root.after(delay_ms, self._finish)

    def _finish(self):
        """Close splash and complete."""
        self.root.destroy()
        self._on_complete()

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
