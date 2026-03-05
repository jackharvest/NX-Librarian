#!/usr/bin/env python3
"""
build_scripts/make_icon.py

Converts logo.png (project root) into:
  icon.ico  — Windows multi-size icon (16, 32, 48, 256)
  icon.icns — macOS icon bundle

Run once from the project root:
    python build_scripts/make_icon.py

Requires: Pillow >= 9.0
"""

import os
import sys
import tempfile
import struct

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required: pip install Pillow")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(ROOT, "logo.png")
ICO  = os.path.join(ROOT, "icon.ico")
ICNS = os.path.join(ROOT, "icon.icns")

ICO_SIZES  = [16, 32, 48, 256]
ICNS_SIZES = [16, 32, 64, 128, 256, 512, 1024]

# ICNS type codes for PNG-compressed icons
ICNS_TYPES = {
    16:   b'icp4',
    32:   b'icp5',
    64:   b'icp6',
    128:  b'ic07',
    256:  b'ic08',
    512:  b'ic09',
    1024: b'ic10',
}


def make_ico(src_image: Image.Image, dest: str):
    sizes = [(s, s) for s in ICO_SIZES]
    images = []
    for size in sizes:
        img = src_image.copy()
        img.thumbnail(size, Image.Resampling.LANCZOS)
        # Pad to exact square with transparency
        padded = Image.new("RGBA", size, (0, 0, 0, 0))
        offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
        padded.paste(img, offset, mask=img.split()[3] if img.mode == "RGBA" else None)
        images.append(padded)

    images[0].save(
        dest,
        format="ICO",
        sizes=[(img.width, img.height) for img in images],
        append_images=images[1:],
    )
    print(f"  Written: {dest}")


def make_icns(src_image: Image.Image, dest: str):
    """
    Build a minimal .icns file by hand — embeds PNG-compressed icons.
    Does not require external tools (iconutil, sips, etc.)
    """
    chunks = []
    for size in ICNS_SIZES:
        code = ICNS_TYPES.get(size)
        if code is None:
            continue
        img = src_image.copy()
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        padded = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        offset = ((size - img.width) // 2, (size - img.height) // 2)
        padded.paste(img, offset, mask=img.split()[3] if img.mode == "RGBA" else None)

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
        try:
            with os.fdopen(tmp_fd, "wb") as fh:
                padded.save(fh, "PNG")
            with open(tmp_path, "rb") as fh:
                png_data = fh.read()
        finally:
            os.unlink(tmp_path)

        # Each chunk: 4-byte type + 4-byte length (includes 8-byte header)
        length = len(png_data) + 8
        chunks.append(code + struct.pack(">I", length) + png_data)

    body = b"".join(chunks)
    total = 8 + len(body)
    with open(dest, "wb") as fh:
        fh.write(b"icns")
        fh.write(struct.pack(">I", total))
        fh.write(body)
    print(f"  Written: {dest}")


def main():
    if not os.path.exists(SRC):
        sys.exit(f"Source not found: {SRC}")

    print(f"Loading: {SRC}")
    src = Image.open(SRC).convert("RGBA")

    print("Generating icon.ico …")
    make_ico(src, ICO)

    print("Generating icon.icns …")
    make_icns(src, ICNS)

    print("Done.")


if __name__ == "__main__":
    main()
