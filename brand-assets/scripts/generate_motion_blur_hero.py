#!/usr/bin/env python3
"""Generate a high-resolution Aethria motion-blur hero asset.

The generator intentionally mirrors the app-front-end brand system:
Oxford blue, warm paper, paper-deep, paper-bright, heritage gold, escalation
burgundy, soft signal blue, Playfair/Georgia wordmark, and mono metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH = 3840
HEIGHT = 1080
SUPERSAMPLE = 2
SEED = 20260518

OUTPUT = Path(__file__).resolve().parent.parent / "assets" / "aethria_motion_blur_hero_4k.png"

PALETTE = {
    "oxford": "#001433",
    "paper": "#f4f1ea",
    "paper_deep": "#e7e0d4",
    "paper_bright": "#f8f5ee",
    "charcoal": "#26313f",
    "heritage_gold": "#a88a5e",
    "escalation": "#7d2b3a",
    "signal_blue": "#c9d9ea",
}


@dataclass(frozen=True)
class TextFonts:
    display: ImageFont.FreeTypeFont | ImageFont.ImageFont
    display_large: ImageFont.FreeTypeFont | ImageFont.ImageFont
    sans: ImageFont.FreeTypeFont | ImageFont.ImageFont
    mono: ImageFont.FreeTypeFont | ImageFont.ImageFont


def hex_rgb(value: str) -> np.ndarray:
    value = value.lstrip("#")
    return np.array([int(value[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def mix(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    return (a * (1.0 - t)) + (b * t)


def resolve_font(candidates: Iterable[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue

    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue

    return ImageFont.load_default(size=size)


def build_fonts(scale: int = 1) -> TextFonts:
    display_candidates = [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Times.ttc",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    ]
    mono_candidates = [
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Monaco.ttf",
        "Menlo.ttc",
        "Courier New.ttf",
    ]
    sans_candidates = [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Avenir Next.ttc",
        "/System/Library/Fonts/Avenir.ttc",
    ]
    return TextFonts(
        display=resolve_font(display_candidates, 68 * scale),
        display_large=resolve_font(display_candidates, 268 * scale),
        sans=resolve_font(sans_candidates, 108 * scale),
        mono=resolve_font(mono_candidates, 24 * scale),
    )


def horizontal_directional_blur(rgb: np.ndarray, radius: int) -> np.ndarray:
    """Box blur on the X axis only, using edge padding and cumulative sums."""
    if radius <= 0:
        return rgb

    kernel = radius * 2 + 1
    padded = np.pad(rgb, ((0, 0), (radius, radius), (0, 0)), mode="edge")
    cumulative = np.cumsum(padded, axis=1, dtype=np.float32)
    cumulative = np.pad(cumulative, ((0, 0), (1, 0), (0, 0)), mode="constant")
    window_sum = cumulative[:, kernel:, :] - cumulative[:, :-kernel, :]
    return np.clip(window_sum / kernel, 0, 255).astype(np.uint8)


def vertical_box_blend(rgb: np.ndarray, radius: int) -> np.ndarray:
    """Low-radius Y-axis averaging to merge strip boundaries after motion blur."""
    if radius <= 0:
        return rgb

    kernel = radius * 2 + 1
    padded = np.pad(rgb, ((radius, radius), (0, 0), (0, 0)), mode="edge")
    cumulative = np.cumsum(padded, axis=0, dtype=np.float32)
    cumulative = np.pad(cumulative, ((1, 0), (0, 0), (0, 0)), mode="constant")
    window_sum = cumulative[kernel:, :, :] - cumulative[:-kernel, :, :]
    return np.clip(window_sum / kernel, 0, 255).astype(np.uint8)


def make_background() -> Image.Image:
    rng = np.random.default_rng(SEED)
    oxford = hex_rgb(PALETTE["oxford"])
    charcoal = hex_rgb(PALETTE["charcoal"])
    paper = hex_rgb(PALETTE["paper"])
    paper_deep = hex_rgb(PALETTE["paper_deep"])
    paper_bright = hex_rgb(PALETTE["paper_bright"])
    gold = hex_rgb(PALETTE["heritage_gold"])
    burgundy = hex_rgb(PALETTE["escalation"])
    blue = hex_rgb(PALETTE["signal_blue"])

    source_height = 96
    arr = np.zeros((source_height, WIDTH, 3), dtype=np.float32)

    y = 0
    while y < source_height:
        strip_h = int(rng.integers(5, 18))
        base = mix(oxford, charcoal, rng.uniform(0.18, 0.42))
        accent_roll = rng.random()
        if accent_roll < 0.38:
            base = mix(base, paper_deep, rng.uniform(0.04, 0.14))
        elif accent_roll < 0.56:
            base = mix(base, blue, rng.uniform(0.03, 0.09))
        elif accent_roll < 0.68:
            base = mix(base, gold, rng.uniform(0.02, 0.09))

        x_grad = np.linspace(0, 1, WIDTH, dtype=np.float32)
        left_t = rng.uniform(-0.10, 0.06)
        right_t = rng.uniform(-0.18, 0.10)
        gradient = np.interp(x_grad, [0, 1], [left_t, right_t])[:, None]
        strip = base + (paper_bright - base) * gradient * 0.38
        strip += rng.normal(0, 0.8, (WIDTH, 3))
        arr[y : min(y + strip_h, source_height), :, :] = strip
        y += strip_h

    low_res = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    arr = np.asarray(low_res.resize((WIDTH, HEIGHT), Image.Resampling.BICUBIC)).astype(np.float32)

    # Long exposure signal streaks before the directional blur pass.
    for _ in range(104):
        y0 = int(rng.integers(-70, HEIGHT + 70))
        h = int(rng.integers(34, 180))
        x0 = int(rng.integers(-WIDTH // 4, WIDTH))
        length = int(rng.integers(WIDTH // 2, WIDTH * 2))
        color = [paper, paper_bright, paper_deep, blue, gold, burgundy, oxford][int(rng.integers(0, 7))]
        alpha = float(rng.uniform(0.008, 0.048))

        x1 = max(0, x0)
        x2 = min(WIDTH, x0 + length)
        yy1 = max(0, y0)
        yy2 = min(HEIGHT, y0 + h)
        if x2 <= x1 or yy2 <= yy1:
            continue

        fade_base = np.clip(np.sin(np.linspace(0, np.pi, x2 - x1, dtype=np.float32)), 0, 1)
        fade = fade_base ** rng.uniform(0.45, 1.2)
        mask = fade[None, :, None] * alpha
        arr[yy1:yy2, x1:x2, :] = arr[yy1:yy2, x1:x2, :] * (1 - mask) + color * mask

    arr = np.clip(arr, 0, 255).astype(np.uint8)
    blurred = horizontal_directional_blur(arr, radius=460)
    blurred = vertical_box_blend(blurred, radius=34)
    blurred = horizontal_directional_blur(blurred, radius=310)
    blurred = vertical_box_blend(blurred, radius=16)

    # Add a darker right-side field, matching the reference image's text area.
    y_axis = np.linspace(-1, 1, HEIGHT, dtype=np.float32)[:, None]
    x_axis = np.linspace(-1, 1, WIDTH, dtype=np.float32)[None, :]
    right_plate = np.clip((x_axis - 0.08) / 0.92, 0, 1) ** 1.2
    vignette = np.clip((x_axis**2 * 0.16) + (y_axis**2 * 0.32) + right_plate * 0.44, 0, 1)
    vignette = vignette[:, :, None]
    dark = hex_rgb(PALETTE["oxford"])[None, None, :]
    blurred = (blurred.astype(np.float32) * (1 - vignette * 0.72) + dark * (vignette * 0.72)).astype(np.uint8)

    return Image.fromarray(blurred, "RGB")


def soft_light(base: np.ndarray, blend: np.ndarray, opacity: float) -> np.ndarray:
    base_norm = base / 255.0
    blend_norm = blend / 255.0
    low = base_norm - (1 - 2 * blend_norm) * base_norm * (1 - base_norm)
    high = base_norm + (2 * blend_norm - 1) * (np.sqrt(np.clip(base_norm, 0, 1)) - base_norm)
    mixed = np.where(blend_norm < 0.5, low, high)
    out = base_norm * (1 - opacity) + mixed * opacity
    return np.clip(out * 255, 0, 255).astype(np.uint8)


def apply_film_grain(image: Image.Image) -> Image.Image:
    rng = np.random.default_rng(SEED + 9)
    base = np.asarray(image).astype(np.float32)
    noise = rng.normal(loc=128.0, scale=38.0, size=(HEIGHT, WIDTH)).clip(0, 255).astype(np.uint8)
    noise_image = Image.fromarray(noise, "L").filter(ImageFilter.GaussianBlur(radius=1.0))
    noise_rgb = np.repeat(np.asarray(noise_image)[:, :, None], 3, axis=2).astype(np.float32)
    grained = soft_light(base, noise_rgb, opacity=0.42)

    # Fine silver halide speckle, extremely low opacity, to avoid plastic flatness.
    micro = rng.normal(loc=0.0, scale=3.4, size=(HEIGHT, WIDTH, 1)).astype(np.float32)
    grained = np.clip(grained.astype(np.float32) + micro, 0, 255).astype(np.uint8)
    return Image.fromarray(grained, "RGB")


def text_bbox(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.ImageFont) -> tuple[int, int, int, int]:
    return draw.textbbox(xy, text, font=font)


def draw_text_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    xy: tuple[int, int],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    line_height: int,
) -> None:
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height


def add_typography(image: Image.Image) -> Image.Image:
    scale = SUPERSAMPLE
    canvas = image.convert("RGBA")
    text_layer = Image.new("RGBA", (WIDTH * scale, HEIGHT * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)
    fonts = build_fonts(scale)

    paper = tuple(hex_rgb(PALETTE["paper_bright"]).astype(int).tolist()) + (236,)
    headline = tuple(hex_rgb(PALETTE["paper"]).astype(int).tolist()) + (240,)
    meta = tuple(hex_rgb(PALETTE["paper"]).astype(int).tolist()) + (118,)

    block_x = 2148 * scale
    brand_y = 152 * scale
    brand = "Aethria"
    draw.text((block_x, brand_y), brand, font=fonts.display, fill=paper)

    headline_lines = ["Discover Signals.", "Score Conviction.", "Move First."]
    draw_text_lines(
        draw,
        headline_lines,
        (block_x, 318 * scale),
        fonts.sans,
        headline,
        line_height=124 * scale,
    )

    draw_text_lines(
        draw,
        ["SCOUT", "REVIEW", "DECIDE"],
        (138 * scale, 780 * scale),
        fonts.mono,
        meta,
        line_height=44 * scale,
    )

    text_layer = text_layer.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)

    # Soft optical glow beneath the sharp typography, then the downsampled text.
    alpha = text_layer.getchannel("A")
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 20, 51, 0))
    glow.putalpha(alpha.filter(ImageFilter.GaussianBlur(radius=4)))
    canvas.alpha_composite(glow)
    canvas.alpha_composite(text_layer)
    return canvas.convert("RGB")


def main() -> None:
    background = make_background()
    grained = apply_film_grain(background)
    final = add_typography(grained)
    final.save(OUTPUT, format="PNG", compress_level=0, optimize=False)
    print(f"Saved {OUTPUT} ({WIDTH}x{HEIGHT}, PNG compress_level=0)")


if __name__ == "__main__":
    main()
