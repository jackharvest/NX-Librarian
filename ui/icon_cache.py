"""
ui/icon_cache.py — Lazy icon download and compositing engine for Art Mode.

Flow:
  1. request_icon(tid, url, ready_cb) starts a background download if needed.
  2. Downloaded images are saved to ~/.nxlibrarian_icons/<tid>.jpg at 128×128.
  3. get_photo() composites a right-aligned, left-fading art strip from the
     cached PIL image and returns a Tk PhotoImage ready to use as an overlay.
  4. Rendered PhotoImages are cached by (tid, w, h, row_bg, hover) so hover
     switches are instant reference-swaps with no PIL work.
"""

import os
import io
import logging
import threading
import configparser

from constants import CONFIG_FILE, HAND_CURSOR

_LOG = logging.getLogger("icon_cache")
_LOG.addHandler(logging.NullHandler())

try:
    from PIL import Image, ImageTk
    _PILLOW = True
except ImportError:
    _PILLOW = False

# ── tunables ────────────────────────────────────────────────────────────────

_DISK_MAX_W      = 800    # px — max width when saving to disk (aspect preserved)
_DISK_MAX_H      = 500    # px — max height when saving to disk (aspect preserved)
_MIN_VALID_BYTES = 40_000 # raw CDN bytes; placeholders are ~29 KB, real art is 600 KB+
_ART_MAX_W       = 730   # px — art never wider than this; slides right as cell grows
_GRAD_SPAN       = 120   # px — left-edge fade from transparent → full opacity
_OPACITY_DIM     = 0.72  # base opacity (art fills full filename cell)
_OPACITY_HOV     = 0.90  # hover opacity
_CELL_PADDING    = 8     # px — text left padding inside art cell
_TEXT_BOTTOM_PAD = 7     # px — text bottom padding inside art cell

# ── module state ────────────────────────────────────────────────────────────

_enabled    = False
_pil_cache: dict       = {}   # tid_lower → PIL Image (RGBA, _DISK_SIZE)
_photo_cache: dict     = {}   # (tid, w, h, bg, hover, text) → ImageTk.PhotoImage
_downloading: set      = set()
_pil_font_cache: dict  = {}   # size → ImageFont
_lock = threading.Lock()

_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".nxlibrarian_icons")


# ── enable / disable ────────────────────────────────────────────────────────

def is_enabled() -> bool:
    return _enabled and _PILLOW


def set_enabled(value: bool):
    global _enabled
    _enabled = value
    try:
        cfg = configparser.ConfigParser()
        cfg.read(CONFIG_FILE)
        if "Settings" not in cfg:
            cfg["Settings"] = {}
        cfg["Settings"]["art_mode"] = "true" if value else "false"
        with open(CONFIG_FILE, "w") as f:
            cfg.write(f)
    except Exception:
        pass


def load_enabled():
    global _enabled
    try:
        cfg = configparser.ConfigParser()
        cfg.read(CONFIG_FILE)
        _enabled = cfg.getboolean("Settings", "art_mode", fallback=False)
    except Exception:
        _enabled = False
    # Photo cache is session-only (ImageTk objects can't be pickled/persisted),
    # so always start fresh — PIL images are loaded from disk cache as needed.
    _photo_cache.clear()


def invalidate_photo_cache():
    """Clear rendered PhotoImages (call after row-height changes)."""
    with _lock:
        _photo_cache.clear()


def clear_icon(tid: str):
    """Remove *tid* from all caches and delete the disk file so it re-downloads."""
    tid = tid.lower()
    with _lock:
        _pil_cache.pop(tid, None)
        _downloading.discard(tid)
        # Drop any cached photos for this tid
        for key in list(_photo_cache.keys()):
            if key[0] == tid:
                _photo_cache.pop(key, None)
    cache_path = os.path.join(_CACHE_DIR, f"{tid}.jpg")
    try:
        os.remove(cache_path)
    except FileNotFoundError:
        pass


# ── icon request ────────────────────────────────────────────────────────────

def request_icon(tid: str, icon_url: str, ready_cb, banner_url: str = ""):
    """
    Ensure an image for *tid* is in the PIL cache.

    Tries banner_url first (1920×1080, ideal for wide rows), then icon_url
    (1024×1024 square, cropped as fallback).  Cached images preserve aspect
    ratio at up to _DISK_MAX_W × _DISK_MAX_H.

    If already cached → calls ready_cb(tid) immediately (still on caller thread).
    If downloading  → no-op; the in-flight thread will call ready_cb when done.
    Otherwise       → starts a background download, calls ready_cb(tid) when ready.

    ready_cb must schedule any Tk updates via widget.after() — it may be called
    from a background thread.
    """
    if not _PILLOW:
        _LOG.warning("request_icon(%s): Pillow not available", tid)
        return
    tid = tid.lower()

    with _lock:
        if tid in _pil_cache:
            _LOG.debug("request_icon(%s): pil_cache hit → calling ready_cb", tid)
            ready_cb(tid)
            return
        if tid in _downloading:
            _LOG.debug("request_icon(%s): already downloading, skipping", tid)
            return
        _downloading.add(tid)

    # Check disk cache before hitting the network
    cache_path = os.path.join(_CACHE_DIR, f"{tid}.jpg")
    if os.path.exists(cache_path):
        try:
            if os.path.getsize(cache_path) < _MIN_VALID_BYTES // 4:
                _LOG.debug("request_icon(%s): disk cache too small (%d bytes, placeholder), purging",
                           tid, os.path.getsize(cache_path))
                os.remove(cache_path)
                raise ValueError("cached placeholder")
            img = Image.open(cache_path).convert("RGBA")
            if img.width < _DISK_MAX_W // 2:
                # Too small — old square-icon cache; discard and re-download as banner
                _LOG.debug("request_icon(%s): disk cache too small (%dpx), re-downloading", tid, img.width)
                os.remove(cache_path)
                raise ValueError("stale")
            with _lock:
                _pil_cache[tid] = img
                _downloading.discard(tid)
            _LOG.debug("request_icon(%s): loaded from disk cache", tid)
            ready_cb(tid)
            return
        except Exception as exc:
            _LOG.warning("request_icon(%s): disk cache invalid (%s), re-downloading", tid, exc)

    urls_to_try = [u for u in [banner_url, icon_url] if u]
    _LOG.info("request_icon(%s): starting background download (banner=%s icon=%s)",
              tid, bool(banner_url), bool(icon_url))

    def _download():
        for url in urls_to_try:
            try:
                import requests
                r = requests.get(url, timeout=12)
                r.raise_for_status()
                if len(r.content) < _MIN_VALID_BYTES:
                    _LOG.warning("request_icon(%s): %s → %d bytes (placeholder), trying next URL",
                                 tid, url, len(r.content))
                    continue
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                img.thumbnail((_DISK_MAX_W, _DISK_MAX_H), Image.Resampling.LANCZOS)
                os.makedirs(_CACHE_DIR, exist_ok=True)
                img.save(cache_path, "JPEG", quality=88)
                rgba = img.convert("RGBA")
                with _lock:
                    _pil_cache[tid] = rgba
                    _downloading.discard(tid)
                _LOG.info("request_icon(%s): download complete from %s", tid, url)
                ready_cb(tid)
                return
            except Exception as exc:
                _LOG.warning("request_icon(%s): URL failed (%s) — %s", tid, url, exc)
        _LOG.error("request_icon(%s): all URLs failed", tid)
        with _lock:
            _downloading.discard(tid)

    threading.Thread(target=_download, daemon=True).start()


# ── compositing ─────────────────────────────────────────────────────────────

def _load_pil_font(size: int):
    """Return a PIL ImageFont for the given size, preferring system TTF."""
    if size in _pil_font_cache:
        return _pil_font_cache[size]
    from PIL import ImageFont
    search_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    font = None
    for path in search_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()
    _pil_font_cache[size] = font
    return font


def get_photo(tid: str, cell_w: int, cell_h: int,
              row_bg: str, hover: bool, overlay_text: str = ""):
    """
    Return a composited PhotoImage for *tid* or None if the icon isn't ready.

    The image is cell_w × cell_h with the game art right-aligned and fading
    to transparent on the left via a gradient.  Results are cached so hover
    transitions (dim↔bright) are zero-cost after the first render.
    """
    if not _PILLOW:
        return None
    tid = tid.lower()
    key = (tid, cell_w, cell_h, row_bg, hover, overlay_text)
    with _lock:
        cached = _photo_cache.get(key)
        pil    = _pil_cache.get(tid)
    if cached:
        return cached
    if pil is None:
        return None

    opacity = _OPACITY_HOV if hover else _OPACITY_DIM
    photo   = _render(pil, cell_w, cell_h, row_bg, opacity, overlay_text)
    with _lock:
        _photo_cache[key] = photo
    return photo


def _hex_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _render(pil_img: "Image.Image", cell_w: int, cell_h: int,
            row_bg: str, opacity: float, overlay_text: str = "") -> "ImageTk.PhotoImage":
    """Composite the icon right-aligned in the filename cell.

    The art is capped at _ART_MAX_W so it never stretches wider than intended.
    When cell_w > _ART_MAX_W the art slides to the right and the extra space
    on the left is filled with the plain row background colour.
    """
    oh    = cell_h
    ow    = min(cell_w, _ART_MAX_W)   # art width — never exceeds max
    x_off = cell_w - ow               # left offset when cell is wider than max

    # Cover-crop: scale icon to fill ow×oh, center-crop any overflow
    src_w, src_h = pil_img.size
    scale  = max(ow / src_w, oh / src_h)
    new_w  = max(ow, int(src_w * scale))
    new_h  = max(oh, int(src_h * scale))
    scaled = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS).convert("RGBA")
    left   = (new_w - ow) // 2
    top    = (new_h - oh) // 2
    icon   = scaled.crop((left, top, left + ow, top + oh))

    # Build left-fade + opacity alpha in one pass:
    # x < _GRAD_SPAN → ramps 0→opacity; x >= _GRAD_SPAN → flat opacity
    fade_end  = min(ow, _GRAD_SPAN)
    row_alpha = [
        int(255 * opacity * (x / fade_end if x < fade_end else 1.0))
        for x in range(ow)
    ]
    grad = Image.new("L", (ow, oh))
    grad.putdata(row_alpha * oh)
    r, g, b, _ = icon.split()
    icon = Image.merge("RGBA", (r, g, b, grad))

    # Composite art over the row background colour
    art_bg = Image.new("RGB", (ow, oh), _hex_rgb(row_bg))
    art    = art_bg.copy()
    art.paste(icon.convert("RGB"), (0, 0), icon)

    # Dark gradient band at the bottom so filename text stays legible
    fade_h    = int(oh * 0.55)
    ramp_data = [int(180 * i / max(fade_h - 1, 1)) for i in range(fade_h)]
    ramp_col  = Image.new("L", (1, fade_h))
    ramp_col.putdata(ramp_data)
    mask = ramp_col.resize((ow, fade_h), Image.Resampling.NEAREST)
    art.paste(Image.new("RGB", (ow, fade_h), (0, 0, 0)), (0, oh - fade_h), mask)

    # Draw filename text at bottom-left of the art strip
    if overlay_text:
        try:
            from PIL import ImageDraw
            font  = _load_pil_font(10)
            draw  = ImageDraw.Draw(art)
            try:
                bbox    = font.getbbox("Ag")
                text_h  = bbox[3] - bbox[1]
                top_off = bbox[1]
            except AttributeError:
                text_h  = 10
                top_off = 0
            text_x = _CELL_PADDING
            text_y = oh - text_h - _TEXT_BOTTOM_PAD - top_off
            draw.text((text_x + 1, text_y + 1), overlay_text, fill=(0, 0, 0),      font=font)
            draw.text((text_x,     text_y),     overlay_text, fill=(255, 255, 255), font=font)
        except Exception:
            pass

    # If the cell is wider than _ART_MAX_W, place art right-aligned on a full-width canvas
    if x_off > 0:
        result = Image.new("RGB", (cell_w, oh), _hex_rgb(row_bg))
        result.paste(art, (x_off, 0))
    else:
        result = art

    return ImageTk.PhotoImage(result)
