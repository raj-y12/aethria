#!/usr/bin/env python3
"""Sun -> #fcfcfc; favicon = square crop centered on A, rounded-corner mask."""
import os
from PIL import Image, ImageDraw

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "web-front-end", "public", "logo.png")
OUT_FAVICON = os.path.join(os.path.dirname(__file__), "..", "web-front-end", "public", "favicon.png")

# Sun/cream -> ivory
CREAM_RGB = (0xF7, 0xF2, 0xE3)
IVORY_RGB = (0xFC, 0xFC, 0xFC)
CREAM_TOLERANCE = 35

BG_RGB = (0x00, 0x21, 0x47)
BG_TOLERANCE = 5

# Zoom: crop square as fraction of image (higher = less cropped, more context)
ZOOM_FRAC = 0.88
ROUND_RADIUS = 72  # rounded corner radius on 512px image


def is_cream(r, g, b):
    return all(abs(c - o) <= CREAM_TOLERANCE for c, o in zip((r, g, b), CREAM_RGB))


def is_bg(r, g, b):
    return all(abs(c - o) <= BG_TOLERANCE for c, o in zip((r, g, b), BG_RGB))


def main():
    img = Image.open(LOGO_PATH).convert("RGBA")
    w, h = img.size
    px = img.load()

    # 1. Sun -> #fcfcfc
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if is_cream(r, g, b):
                px[x, y] = (*IVORY_RGB, a)
    img.save(LOGO_PATH, "PNG")

    # 2. Content center (A)
    x_min, y_min, x_max, y_max = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            if not is_bg(r, g, b):
                x_min = min(x_min, x)
                y_min = min(y_min, y)
                x_max = max(x_max, x)
                y_max = max(y_max, y)
    cx = (x_min + x_max) // 2
    cy = (y_min + y_max) // 2

    # 3. Square crop, zoomed in (tighter on emblem for clarity)
    base_side = min(w, h)
    crop_side = int(base_side * ZOOM_FRAC)
    crop_side = max(crop_side, 32)
    left = cx - crop_side // 2
    top = cy - crop_side // 2
    left = max(0, min(left, w - crop_side))
    top = max(0, min(top, h - crop_side))
    box = (left, top, left + crop_side, top + crop_side)
    square = img.crop(box)
    # Resize to 512 for sharp favicon at 32px
    square = square.resize((512, 512), Image.Resampling.LANCZOS)
    # Rounded-rectangle mask (square with rounded corners, transparent outside)
    mask = Image.new("L", (512, 512), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, 511, 511), radius=ROUND_RADIUS, fill=255)
    square.putalpha(mask)

    os.makedirs(os.path.dirname(OUT_FAVICON), exist_ok=True)
    square.save(OUT_FAVICON, "PNG")
    print("Favicon: square with rounded corners (A centered), 512px.")


if __name__ == "__main__":
    main()
