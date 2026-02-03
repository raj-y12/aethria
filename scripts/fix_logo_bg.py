#!/usr/bin/env python3
"""Replace logo background #1A2F49 with #002147. Saves over original and copies favicon."""
import os
from PIL import Image

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "web-front-end", "public", "logo.png")
OUT_FAVICON = os.path.join(os.path.dirname(__file__), "..", "web-front-end", "public", "favicon.png")

# Current background (and 'A' color) -> target Oxford blue
OLD_RGB = (0x1A, 0x2F, 0x49)  # #1A2F49
NEW_RGB = (0x00, 0x21, 0x47)  # #002147
TOLERANCE = 12  # match near-matches (anti-aliasing)

def main():
    img = Image.open(LOGO_PATH).convert("RGBA")
    w, h = img.size
    px = img.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if all(abs(c - o) <= TOLERANCE for c, o in zip((r, g, b), OLD_RGB)):
                px[x, y] = (*NEW_RGB, a)
    img.save(LOGO_PATH, "PNG")
    os.makedirs(os.path.dirname(OUT_FAVICON), exist_ok=True)
    img.save(OUT_FAVICON, "PNG")
    print("Updated logo.png background to #002147 and wrote web-front-end/public/favicon.png")

if __name__ == "__main__":
    main()
