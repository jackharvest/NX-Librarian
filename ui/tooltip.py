"""
ui/tooltip.py — Dark HUD-style info panel tooltip.

Key design decision: the Tk canvas background is set to the same colour as
the card body (#0b0b18).  There are no transparent pixels — the "rectangle
problem" vanishes because the rectangle IS the card.

After the cursor has been still inside the target widget for HOVER_S seconds
the card grows downward from a fixed top edge using spring physics.
"""

import sys
import math
import time
import tkinter as tk

# ── Module-level enable/disable ───────────────────────────────────────────────
_enabled = True

def set_enabled(value: bool):
    global _enabled
    _enabled = value

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    _PILLOW = True
except ImportError:
    _PILLOW = False

# ── Tuning ────────────────────────────────────────────────────────────────────
HOVER_S   = 1.5    # seconds of stillness before showing
POLL_MS   = 100
MOVE_SLOP = 4

# ── Card geometry ─────────────────────────────────────────────────────────────
CARD_W  = 276
PAD     = 16       # inner horizontal/vertical padding
BORDER  = 3        # accent stripe thickness (left + top)
LINE_H  = 20
FONT_SZ = 11

# ── Spring — damped so height doesn't overshoot ───────────────────────────────
_ZETA  = 0.65
_OMEGA = 26.0

# ── Palette ───────────────────────────────────────────────────────────────────
_BG_RGB = (11, 11, 24)          # #0b0b18  ← MUST match _BG_HEX exactly
_BG_HEX = "#0b0b18"
_RIM    = (28, 28, 52, 255)     # 1-px outer rim, slightly lighter than bg
_TXT    = (210, 210, 235, 255)  # body text
_DIM    = (90,  95, 125, 255)   # secondary / dimmed text


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


class ComicTooltip:
    """
    Dark HUD tooltip.  Appears after the cursor has been still inside
    *widget* for HOVER_S seconds.

        ComicTooltip(widget, "Helpful text", accent_color="#e74c55")
    """

    def __init__(self, widget: tk.Widget, text: str, accent_color: str = "#60a5fa"):
        self._w          = widget
        self._text       = text
        self._accent_rgb = _hex_to_rgb(accent_color)

        self._win        = None
        self._canvas     = None
        self._img_ref    = None
        self._pil_base   = None
        self._bw = self._bh = 0
        self._t0         = 0.0
        self._animating  = False
        self._tx = self._ty = 0

        self._last_pos    = (-9999, -9999)
        self._idle_since  = time.time()
        self._poll_id     = None
        self._app_focused = True   # fallback for non-Windows

        # On Linux/macOS: FocusIn/FocusOut on the WM toplevel is reliable.
        # On Windows we use GetForegroundWindow() in _app_has_focus() instead.
        if sys.platform != "win32":
            try:
                tl = widget.winfo_toplevel()
                tl.bind("<FocusIn>",  lambda e: setattr(self, "_app_focused", True),  add="+")
                tl.bind("<FocusOut>", lambda e: setattr(self, "_app_focused", False), add="+")
            except Exception:
                pass

        self._start_polling()

    # ── Focus check ───────────────────────────────────────────────────────────

    def _app_has_focus(self) -> bool:
        """Return True only if our app window is the OS foreground window.

        On Windows, tkinter's FocusOut is unreliable for app-level switching,
        so we ask Win32 directly.  On other platforms the event-tracked flag
        is accurate enough.
        """
        if sys.platform == "win32":
            try:
                import ctypes
                fg   = ctypes.windll.user32.GetForegroundWindow()
                tl   = self._w.winfo_toplevel()
                hwnd = tl.winfo_id()
                # Tk gives us the client HWND; the visible frame is its parent
                parent = ctypes.windll.user32.GetParent(hwnd)
                return fg in (hwnd, parent)
            except Exception:
                pass
        return self._app_focused

    # ── Polling ───────────────────────────────────────────────────────────────

    def _start_polling(self):
        self._poll_id = self._w.after(POLL_MS, self._poll)

    def _poll(self):
        try:
            # Widget destroyed — stop polling entirely
            if not self._w.winfo_exists():
                self._hide()
                return

            # Tooltips globally disabled
            if not _enabled:
                self._hide()
                self._last_pos   = (-9999, -9999)
                self._idle_since = time.time()
                self._poll_id = self._w.after(POLL_MS, self._poll)
                return

            # Widget hidden (navigated away) — suppress tooltip, keep polling
            if not self._w.winfo_ismapped():
                self._hide()
                self._last_pos   = (-9999, -9999)
                self._idle_since = time.time()
                self._poll_id = self._w.after(POLL_MS, self._poll)
                return

            if not self._app_has_focus():
                self._hide()
                self._last_pos   = (-9999, -9999)
                self._idle_since = time.time()
                self._poll_id = self._w.after(POLL_MS, self._poll)
                return

            px, py = self._w.winfo_pointerxy()
            wx = self._w.winfo_rootx()
            wy = self._w.winfo_rooty()
            ww = self._w.winfo_width()
            wh = self._w.winfo_height()

            inside = wx <= px <= wx + ww and wy <= py <= wy + wh

            if inside:
                dx = abs(px - self._last_pos[0])
                dy = abs(py - self._last_pos[1])
                if dx > MOVE_SLOP or dy > MOVE_SLOP:
                    self._last_pos   = (px, py)
                    self._idle_since = time.time()
                    self._hide()
                else:
                    if time.time() - self._idle_since >= HOVER_S and not self._win:
                        self._show(px, py)
            else:
                self._last_pos   = (-9999, -9999)
                self._idle_since = time.time()
                self._hide()

        except Exception:
            pass

        self._poll_id = self._w.after(POLL_MS, self._poll)

    # ── Show / hide ───────────────────────────────────────────────────────────

    def _hide(self):
        self._animating = False
        if self._win:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = self._canvas = self._img_ref = None

    # ── Image construction ────────────────────────────────────────────────────

    def _load_font(self, size):
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/segoeui.ttf",
        ]:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _wrap_text(self, font, text: str, max_w: int) -> list:
        words, lines, line = text.split(), [], ""
        for word in words:
            candidate = (line + " " + word).strip()
            try:
                w = font.getlength(candidate)
            except AttributeError:
                w = font.getsize(candidate)[0]
            if w > max_w and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        return lines

    def _build_image(self):
        font    = self._load_font(FONT_SZ)
        inner_w = CARD_W - BORDER - PAD * 2
        lines   = self._wrap_text(font, self._text, inner_w)

        # Height: border + top-pad + text rows + bottom-pad + chevron-area
        chevron_h = 10
        card_h    = BORDER + PAD + len(lines) * LINE_H + PAD + chevron_h

        img  = Image.new("RGBA", (CARD_W, card_h), _BG_RGB + (255,))
        draw = ImageDraw.Draw(img)
        acc  = self._accent_rgb

        # ── Outer rim (1 px, slightly lighter than bg) ────────────────────────
        draw.rectangle([0, 0, CARD_W - 1, card_h - 1], outline=_RIM, width=1)

        # ── Left accent stripe ────────────────────────────────────────────────
        draw.rectangle([0, 0, BORDER - 1, card_h - 1], fill=acc + (255,))

        # ── Top accent stripe ─────────────────────────────────────────────────
        draw.rectangle([0, 0, CARD_W - 1, BORDER - 1], fill=acc + (255,))

        # ── Corner bracket — bottom-right targeting mark ──────────────────────
        clen, ct = 11, 2
        bx = CARD_W - 2
        by = card_h - chevron_h - 2
        draw.rectangle([bx - clen, by - ct + 1, bx, by], fill=acc + (150,))
        draw.rectangle([bx - ct + 1, by - clen, bx, by], fill=acc + (150,))

        # ── Body text ─────────────────────────────────────────────────────────
        y = BORDER + PAD
        for line in lines:
            draw.text((BORDER + PAD, y), line, fill=_TXT, font=font)
            y += LINE_H

        # ── Bottom chevron — points at the cursor below ───────────────────────
        cx   = CARD_W // 2
        cy   = card_h - 4
        half = 9
        draw.line([(cx - half, cy - 5), (cx,       cy)], fill=acc + (180,), width=2)
        draw.line([(cx,        cy),      (cx + half, cy - 5)], fill=acc + (180,), width=2)

        self._pil_base = img
        self._bw       = CARD_W
        self._bh       = card_h

    # ── Show & height-reveal animation ───────────────────────────────────────

    def _show(self, cursor_x: int, cursor_y: int):
        if not _PILLOW:
            return
        self._build_image()
        if not self._pil_base:
            return

        sw = self._w.winfo_screenwidth()
        sh = self._w.winfo_screenheight()

        # Card floats above cursor; chevron at bottom points downward
        tx = cursor_x - self._bw // 2
        ty = cursor_y - self._bh - 10

        if ty < 4:           # not enough room above — show below cursor
            ty = cursor_y + 10

        tx = max(4, min(tx, sw - self._bw - 4))

        self._tx = tx
        self._ty = ty

        # ── Toplevel ─────────────────────────────────────────────────────────
        self._win = tk.Toplevel(self._w.winfo_toplevel())
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)

        # Background = card body colour → no visible rectangle
        self._win.configure(bg=_BG_HEX)
        self._canvas = tk.Canvas(self._win, width=self._bw, height=1,
                                 bg=_BG_HEX, highlightthickness=0)
        self._canvas.pack()

        # Start with height=1 at the final top position; grows downward
        self._win.geometry(f"{self._bw}x1+{tx}+{ty}")

        # Image pinned to canvas top-left — canvas height clips it
        self._img_ref = ImageTk.PhotoImage(self._pil_base)
        self._canvas.create_image(0, 0, image=self._img_ref, anchor="nw")

        self._t0        = time.time()
        self._animating = True
        self._tick()

    @staticmethod
    def _spring(t: float) -> float:
        if t <= 0:
            return 0.0
        denom = math.sqrt(max(1e-9, 1 - _ZETA ** 2))
        wd    = _OMEGA * denom
        return 1 - math.exp(-_ZETA * _OMEGA * t) * (
            math.cos(wd * t) + (_ZETA / denom) * math.sin(wd * t)
        )

    def _tick(self):
        if not self._animating or not self._win:
            return
        try:
            if not self._win.winfo_exists():
                return
        except Exception:
            return

        t = time.time() - self._t0
        # Clamp spring to [0, 1] so height never exceeds the full card
        s = max(0.0, min(1.0, self._spring(t)))
        h = max(1, int(self._bh * s))

        try:
            self._win.geometry(f"{self._bw}x{h}+{self._tx}+{self._ty}")
            self._canvas.configure(height=h)
        except Exception:
            return

        if t < 0.65:
            self._win.after(16, self._tick)
        else:
            self._animating = False
