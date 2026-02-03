#!/usr/bin/env python3
"""Sun -> #fcfcfc, favicon square crop centered on the A, circular mask."""
import os
from PIL import Image, ImageDraw

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "web-front-end", "public", "logo.png")
OUT_FAVICON = os.path.join(os.path.dirname(__file__), "..", "web-front-end", "public", "favicon.png")

# Sun/cream -> ivory
CREAM_RGB = (0xF7, 0xF2, 0xE3)  # approximate cream
IVORY_RGB = (0xFC, 0xFC, 0xFC)  # #fcfcfc
CREAM_TOLERANCE = 35  # match cream and near-cream

# Background (ignore when finding content center)
BG_RGB = (0x00, 0x21, 0x47)
BG_TOLERANCE = 5


def is_cream(r, g, b):
    return all(abs(c - o) <= CREAM_TOLERANCE for c, o in zip((r, g, b), CREAM_RGB))


def is_bg(r, g, b):
    return all(abs(c - o) <= BG_TOLERANCE for c, o in zip((r, g, b), BG_RGB))


def main():
    img = Image.open(LOGO_PATH).convert("RGBA")
    w, h = img.size
    px = img.load()

    # 1. Change sun (cream) to #fcfcfc
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if is_cream(r, g, b):
                px[x, y] = (*IVORY_RGB, a)
    img.save(LOGO_PATH, "PNG")

    # 2. Find content center (non-background pixels) so A is in the middle
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

    # 3. Square crop centered on content (A)
    side = min(w, h)
    left = cx - side // 2
    top = cy - side // 2
    left = max(0, min(left, w - side))
    top = max(0, min(top, h - side))
    box = (left, top, left + side, top + side)
    square = img.crop(box)

    # 4. Circular mask
    mask = Image.new("L", (side, side), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, side - 1, side - 1), fill=255)
    square.putalpha(mask)

    os.makedirs(os.path.dirname(OUT_FAVICON), exist_ok=True)
    square.save(OUT_FAVICON, "PNG")
    print("Sun -> #fcfcfc in logo.png; favicon square centered on A, circular mask saved.")


if __name__ == "__main__":
    main()
