"""
ui/custom_cursor.py — Custom Mario/Luigi cursor system.

macOS : uses PyObjC (NSCursor) for native full-color PNG cursors.
Windows: falls back to .cur files if present, otherwise no-op.

Usage
-----
    mgr = CustomCursorManager(root, mario_path, luigi_path)
    mgr.activate()          # call once after the UI is built
    mgr.rescan(widget)      # call whenever new widgets are added
"""

import sys
import tkinter as tk

# ── Hotspot in the 128×128 source image (uppermost fingertip) ─────────
_SRC_HOTSPOT = (20, 2)
_SRC_SIZE    = 128
CURSOR_SIZE  = 48   # pixels to display the cursor at


# ══════════════════════════════════════════════════════════════════════
# macOS — native NSCursor via PyObjC
# ══════════════════════════════════════════════════════════════════════

def _build_nscursor(png_path: str, display_size: int, hotspot):
    """Load a PNG and return an NSCursor sized to *display_size*."""
    from AppKit import NSCursor, NSImage
    from Foundation import NSData, NSPoint, NSSize

    data = NSData.dataWithContentsOfFile_(png_path)
    img  = NSImage.alloc().initWithData_(data)
    img.setSize_(NSSize(display_size, display_size))

    scale = display_size / _SRC_SIZE
    hx    = hotspot[0] * scale
    hy    = hotspot[1] * scale
    return NSCursor.alloc().initWithImage_hotSpot_(img, NSPoint(hx, hy))


class _MacCursorBackend:
    def __init__(self, mario_path, luigi_path):
        from AppKit import NSCursor
        sz = CURSOR_SIZE
        self.mario  = _build_nscursor(mario_path,  sz, _SRC_HOTSPOT)
        self.luigi  = _build_nscursor(luigi_path,  sz, _SRC_HOTSPOT)
        self.system = NSCursor.arrowCursor()
        self._cur   = None          # 'mario' | 'luigi' | None

    def show_mario(self):
        if self._cur != "mario":
            self.mario.set()
            self._cur = "mario"

    def show_luigi(self):
        if self._cur != "luigi":
            self.luigi.set()
            self._cur = "luigi"

    def restore(self):
        if self._cur is not None:
            self.system.set()
            self._cur = None


# ══════════════════════════════════════════════════════════════════════
# Windows — .cur file backend (optional; gracefully absent)
# ══════════════════════════════════════════════════════════════════════

class _WinCursorBackend:
    """No-op placeholder — Windows .cur support can be added later."""
    def show_mario(self): pass
    def show_luigi(self): pass
    def restore(self):    pass


# ══════════════════════════════════════════════════════════════════════
# CustomCursorManager — platform-agnostic facade
# ══════════════════════════════════════════════════════════════════════

class CustomCursorManager:

    def __init__(self, root: tk.Tk, mario_path: str, luigi_path: str):
        self.root           = root
        self._hoverable     = set()   # widgets that originally had cursor='hand2'
        self._pending_luigi = False   # current desired cursor state

        if sys.platform == "darwin":
            self._backend = _MacCursorBackend(mario_path, luigi_path)
        else:
            self._backend = _WinCursorBackend()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def activate(self):
        """
        Start the custom cursor.  Call once after the initial UI is built.
        Suppresses tkinter's own cursor on all existing widgets and begins
        tracking motion to switch Mario ↔ Luigi.
        """
        self.root.configure(cursor="none")
        self.rescan()
        self.root.bind_all("<Motion>", self._on_motion, add="+")
        self.root.bind_all("<Enter>",  self._on_enter,  add="+")
        self.root.bind(    "<Leave>",  self._on_leave,  add="+")
        self._backend.show_mario()
        self._keep_alive()   # start the persistent cursor refresh loop

    def rescan(self, widget=None):
        """
        Walk the widget tree under *widget* (default: root), suppress
        hand2 cursors, and register those widgets as hoverable.
        Call this after new screens are added.
        """
        self._scan(widget or self.root)

    # ------------------------------------------------------------------
    # Keep-alive loop
    # ------------------------------------------------------------------

    def _keep_alive(self):
        """
        Re-assert NSCursor every 16 ms.

        macOS cursor-rect tracking runs outside the Tk event loop and
        continuously overrides NSCursor.set().  Calling set() again on
        each timer tick wins the race without any visible flicker because
        the 'none' cursor (transparent) is what gets briefly shown, not
        the system arrow.
        """
        if self._pending_luigi:
            self._backend.show_luigi()
        else:
            self._backend.show_mario()
        self.root.after(16, self._keep_alive)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _scan(self, w):
        try:
            cur = w.cget("cursor")
            if cur in ("hand2", "hand"):
                w.configure(cursor="none")
                self._hoverable.add(w)
            elif cur and cur not in ("none", "", "arrow"):
                w.configure(cursor="none")
        except tk.TclError:
            pass
        try:
            for child in w.winfo_children():
                self._scan(child)
        except tk.TclError:
            pass

    def _on_enter(self, event):
        """Catch hand2 the moment the cursor enters a new widget."""
        w = event.widget
        try:
            cur = w.cget("cursor")
            if cur in ("hand2", "hand"):
                w.configure(cursor="none")
                self._hoverable.add(w)
        except tk.TclError:
            pass

    def _on_motion(self, event):
        w = event.widget

        # Catch widgets that set cursor='hand2' dynamically (e.g. treeview)
        use_luigi = False
        try:
            cur = w.cget("cursor")
            if cur in ("hand2", "hand"):
                w.configure(cursor="none")
                self._hoverable.add(w)
                use_luigi = True
            elif cur and cur not in ("none", "", "arrow"):
                w.configure(cursor="none")
        except tk.TclError:
            pass

        if not use_luigi and w in self._hoverable:
            use_luigi = True

        self._pending_luigi = use_luigi

        # after(0) fires after the current event finishes but before the
        # next one — faster than after_idle (which waits for full idleness
        # and never fires during continuous mouse movement).
        fn = self._backend.show_luigi if use_luigi else self._backend.show_mario
        self.root.after(0, fn)

    def _on_leave(self, event):
        """Restore the system cursor when the mouse leaves the app window."""
        rx = self.root.winfo_rootx();  ry = self.root.winfo_rooty()
        rw = self.root.winfo_width();  rh = self.root.winfo_height()
        if not (rx <= event.x_root <= rx + rw and
                ry <= event.y_root <= ry + rh):
            self._backend.restore()
